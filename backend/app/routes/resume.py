"""Resume generation API route — supports NVIDIA and Ollama providers."""

import datetime
import json
import logging
import os

import httpx

from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db, manager
from app.models import Job
from services.ollama_service import NVIDIA_ANALYZE_MODEL
from telegram_processor.config import OLLAMA_BASE_URL
from app.routes.settings import get_analyze_provider, get_resume_provider, get_ollama_model

logger = logging.getLogger(__name__)

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "qwen/qwen3.5-397b-a17b")

def _get_system_prompt() -> str:
    current_year = datetime.datetime.now().year
    return (
        "You are a senior professional resume writer. "
        "Your task is to create a wonderful, attractive, and highly detailed Chinese resume "
        "that will be used as a sample resume for candidates applying to jobs. "
        "The resume must be written in Chinese and tailored precisely to the given job description.\n\n"
        f"CURRENT YEAR: {current_year}. "
        f"The most recent work/project end date must be {current_year}. "
        "All dates must be logically consistent, non-overlapping, and span exactly 8 years "
        f"of total experience ending in {current_year}.\n\n"
        "CANDIDATE PROFILE:\n"
        "- Exactly 8 years of relevant work experience\n"
        "- Worked at exactly 4 companies in total\n"
        "- ONE of the 4 companies MUST be a real, well-known Chinese IT giant "
        "(choose ONE from: ByteDance, Huawei, Xiaomi, JD.com, NetEase, Meituan, Didi, "
        "Bilibili, Kuaishou, Pinduoduo, OPPO, Lenovo). "
        "The other 3 must be real but less famous mid-to-large Chinese tech companies "
        "(believable real names, not placeholders).\n"
        "- Bachelor's degree from a real Chinese university ranked 50-150 nationally\n"
        "- More than 10 projects total across all 4 companies (2-4 projects per company)\n\n"
        "RESUME STRUCTURE — output ONLY these sections in this order:\n"
        "1. 个人简介 (Professional Summary): 8-12 sentences (~250-350 chars), "
        "compelling narrative covering years of experience, core strengths, domain expertise, "
        "and alignment with the job description.\n"
        "2. 专业技能 (Technical Skills): categorized list covering ALL key technologies, "
        "frameworks, tools, and methodologies from the job description. "
        "For the most critical skills, briefly note proficiency and real usage context.\n"
        "3. 工作经历 (Work Experience): exactly 4 companies. Each entry must include:\n"
        "   - Real company name, employment period (Month YYYY - Month YYYY or present), job title\n"
        "   - Key technologies used at this company\n"
        "   - 4-6 detailed bullet points covering: specific responsibilities, "
        "technical decisions, problems encountered and how they were resolved, "
        "business impact, team size/role, quantified achievements "
        "(e.g. % improvement, QPS, cost savings, user growth)\n"
        "4. 项目经历 (Project Experience): 10+ projects total distributed across the 4 companies. "
        "Each project must include:\n"
        "   - Project name (real, specific name) and time period "
        "(must fall within the employing company's tenure)\n"
        "   - 项目背景: project goal, business context, scale (users/traffic/data volume), "
        "key technical challenges\n"
        "   - 技术栈: core technologies, frameworks, middleware, tools used with brief rationale\n"
        "   - 遇到的问题与解决方案: specific technical problems encountered during the project "
        "and detailed explanations of how each was investigated and resolved\n"
        "   - 核心贡献: 4-6 bullet points starting with 主导/负责/参与, each with quantified outcome\n"
        "5. 教育背景 (Education): Bachelor's degree only, real Chinese university ranked 50-150 "
        "nationally, include major, graduation year, and 2-3 relevant courses or research areas.\n\n"
        "STRICT RULES:\n"
        "- Output ONLY the resume text. No preamble, no commentary, no explanation before or after.\n"
        "- Do NOT include any contact information (no phone, email, address, WeChat, LinkedIn, etc.)\n"
        "- Do NOT include any '附加信息', '兴趣爱好', '证书', or standalone '自我评价' sections\n"
        "- Use plain text only — no markdown, no asterisks, no special bullet symbols\n"
        "- All company names, university names, and project names must be REAL and SPECIFIC — "
        "absolutely no placeholders like 【公司A】, 【大学名称】, 【项目X】\n"
        "- Timeline must be perfectly consistent: project dates fall within company tenure, "
        f"no overlapping company periods, total span = exactly 8 years ending {current_year}\n"
        "- Use strong action verbs and quantify every achievement possible\n"
        "- Naturally weave in job description keywords throughout all sections"
    )


def _build_prompt(job_description: str) -> str:
    current_year = datetime.datetime.now().year
    return (
        f"Please create a wonderful, attractive, and highly detailed Chinese resume "
        f"for a candidate applying to the following job. "
        f"This resume will be used as a sample resume for candidates.\n\n"
        f"Job Description:\n---\n{job_description}\n---\n\n"
        f"Requirements:\n"
        f"- Exactly 8 years of experience, exactly 4 companies, 10+ projects total "
        f"(2-4 projects per company), ending in {current_year}\n"
        f"- ONE of the 4 companies must be a real famous Chinese IT company "
        f"(e.g. ByteDance, Huawei, Xiaomi, JD.com, NetEase, Meituan, Didi, Bilibili, "
        f"Kuaishou, Pinduoduo, OPPO, Lenovo); the other 3 are real but less famous\n"
        f"- Each company entry must include: key technologies used, detailed responsibilities, "
        f"specific problems encountered, and exactly how those problems were resolved\n"
        f"- Each project must include: background/context/scale, tech stack with rationale, "
        f"specific problems and resolutions, and quantified contributions (主导/负责/参与 bullets)\n"
        f"- Bachelor's degree from a real Chinese university ranked 50-150 nationally\n"
        f"- NO contact information section, NO additional info / hobbies / certificates section\n"
        f"- All company, university, and project names must be REAL — absolutely no placeholders\n"
        f"- Dates must be perfectly consistent: no overlapping company tenures, "
        f"all projects fall within their company's period, most recent date is {current_year}\n"
        f"- Output ONLY the resume text, nothing else"
    )


def _build_job_description(job: Job) -> str:
    """Build a job description string from a Job ORM object."""
    parts = []
    if job.title:
        parts.append(f"职位：{job.title}")
    if job.company:
        parts.append(f"公司：{job.company}")
    if job.location:
        parts.append(f"地点：{job.location}")
    if job.role_type:
        parts.append(f"岗位类型：{job.role_type}")
    if job.is_remote is not None:
        parts.append(f"远程：{'是' if job.is_remote else '否'}")
    if job.skills:
        skills = job.skills if isinstance(job.skills, list) else [job.skills]
        parts.append(f"技能要求：{', '.join(skills)}")
    if job.summary:
        parts.append(f"\n职位描述：\n{job.summary}")
    if job.translated_text:
        parts.append(f"\n英文原文：\n{job.translated_text}")
    return "\n".join(parts)


ENHANCE_SYSTEM_PROMPT = """你是一位专业的简历优化顾问。你的任务是根据目标职位描述，对用户提供的简历进行深度优化和针对性改写。

优化原则：
- 保留用户简历中真实的工作经历、公司名称、项目名称、时间线
- 重点突出与职位描述高度匹配的技能和经验
- 用更有力的动词和量化数据改写工作/项目描述
- 在自我评价和技能部分自然融入职位描述中的关键词
- 如职位描述要求某项技能而简历中未提及，可在相关项目中合理强化已有的类似技能
- 不虚构没有任何基础的经历
- 严禁修改姓名、联系方式、公司名、学校名等事实性信息
- 只输出优化后的完整简历文本，不要添加任何注释或说明"""

SCORE_SYSTEM_PROMPT = """你是一位专业的招聘顾问，擅长评估简历与职位描述的匹配程度。

请分析简历与职位的匹配度，输出严格的JSON格式（无markdown）：
{
  "score": <0-100的整数>,
  "level": "excellent|good|fair|poor",
  "summary": "<2-3句总体评价>",
  "matched_skills": ["<技能1>", "<技能2>"],
  "missing_skills": ["<技能1>", "<技能2>"],
  "strengths": ["<优势1>", "<优势2>", "<优势3>"],
  "improvements": ["<改进建议1>", "<改进建议2>"]
}

评分标准：
- 90-100: 技能高度吻合，经验完全匹配
- 70-89: 大部分要求满足，少数缺口
- 50-69: 部分匹配，有明显技能缺口
- 0-49: 匹配度低，需大量补充"""


class ResumeGenerateRequest(BaseModel):
    job_id: int | None = None
    message_text: str | None = None


class ResumeEnhanceRequest(BaseModel):
    job_id: int | None = None
    message_text: str | None = None
    resume_text: str


class ResumeScoreRequest(BaseModel):
    job_id: int | None = None
    message_text: str | None = None
    resume_text: str


async def _ollama_stream(system_prompt: str, user_prompt: str, temperature: float = 0.4):
    """Stream tokens from Ollama /api/chat and yield SSE data lines."""
    payload = {
        "model": get_ollama_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise RuntimeError(f"Ollama error {response.status_code}: {body[:200]}")
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield f"data: {json.dumps({'content': content})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
                except json.JSONDecodeError:
                    continue


async def _ollama_complete(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """Call Ollama non-streaming and return the full response text."""
    payload = {
        "model": get_ollama_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()


def register_resume_routes(app):
    """Register resume generation routes."""

    @app.get("/api/resume/provider")
    async def api_resume_provider():
        """Return the currently configured resume AI provider."""
        rp = get_resume_provider()
        return {
            "provider": rp,
            "model": NVIDIA_MODEL if rp == "nvidia" else get_ollama_model(),
            "nvidia_configured": bool(NVIDIA_API_KEY),
        }

    @app.get("/api/analyze/provider")
    async def api_analyze_provider():
        """Return the currently configured message analysis AI provider."""
        ap = get_analyze_provider()
        return {
            "provider": ap,
            "model": NVIDIA_ANALYZE_MODEL if ap == "nvidia" else get_ollama_model(),
            "nvidia_configured": bool(NVIDIA_API_KEY),
        }

    @app.post("/api/resume/generate")
    async def api_generate_resume(
        request: ResumeGenerateRequest,
        db: AsyncSession = Depends(get_db),
    ):
        """Generate a tailored resume for a job posting (streaming). Provider: NVIDIA or Ollama."""
        if get_resume_provider() == "nvidia" and not NVIDIA_API_KEY:
            raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured. Set RESUME_PROVIDER=ollama to use local Ollama instead.")

        if request.job_id:
            result = await db.execute(select(Job).filter(Job.id == request.job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            job_description = _build_job_description(job)
            job_title = job.title or job.company or f"Job #{request.job_id}"
        elif request.message_text:
            job_description = request.message_text.strip()
            job_title = "Message"
        else:
            raise HTTPException(status_code=400, detail="Either job_id or message_text is required")

        if not job_description.strip():
            raise HTTPException(status_code=400, detail="Job has no description to generate resume from")

        prompt = _build_prompt(job_description)
        _job_id = request.job_id or 0

        async def stream_resume():
            await manager.broadcast({"type": "resume_generating", "job_id": _job_id, "job_title": job_title})
            try:
                if get_resume_provider() == "ollama":
                    async for sse in _ollama_stream(_get_system_prompt(), prompt, temperature=0.4):
                        yield sse
                else:
                    payload = {
                        "model": NVIDIA_MODEL,
                        "messages": [
                            {"role": "system", "content": _get_system_prompt()},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 8192,
                        "temperature": 0.4,
                        "top_p": 0.95,
                        "top_k": 20,
                        "presence_penalty": 0,
                        "repetition_penalty": 1,
                        "stream": True,
                    }
                    headers = {
                        "Authorization": f"Bearer {NVIDIA_API_KEY}",
                        "Accept": "text/event-stream",
                        "Content-Type": "application/json",
                    }
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        async with client.stream("POST", NVIDIA_INVOKE_URL, headers=headers, json=payload) as response:
                            if response.status_code != 200:
                                body = await response.aread()
                                logger.error(f"[RESUME] NVIDIA API error {response.status_code}: {body[:200]}")
                                yield f"data: {json.dumps({'error': f'NVIDIA API error: {response.status_code}'})}\n\n"
                                return
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                if line.startswith("data:"):
                                    data = line[5:].strip()
                                    if data == "[DONE]":
                                        yield "data: [DONE]\n\n"
                                        return
                                    try:
                                        chunk = json.loads(data)
                                        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                    except json.JSONDecodeError:
                                        continue
            except Exception as e:
                logger.error(f"[RESUME] Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                await manager.broadcast({"type": "resume_complete", "job_id": _job_id})

        return StreamingResponse(
            stream_resume(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/resume/enhance")
    async def api_enhance_resume(
        request: ResumeEnhanceRequest,
        db: AsyncSession = Depends(get_db),
    ):
        """Enhance user's existing resume tailored to a specific job (streaming). Provider: NVIDIA or Ollama."""
        if get_resume_provider() == "nvidia" and not NVIDIA_API_KEY:
            raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured. Set RESUME_PROVIDER=ollama to use local Ollama instead.")

        if not request.resume_text.strip():
            raise HTTPException(status_code=400, detail="Resume text is required")

        if request.job_id:
            result = await db.execute(select(Job).filter(Job.id == request.job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            job_description = _build_job_description(job)
        elif request.message_text:
            job_description = request.message_text.strip()
        else:
            raise HTTPException(status_code=400, detail="Either job_id or message_text is required")

        prompt = f"""请根据以下职位描述，对用户提供的简历进行针对性优化改写。

职位描述：
---
{job_description}
---

用户现有简历：
---
{request.resume_text}
---

请输出优化后的完整简历文本。"""

        async def stream_enhance():
            try:
                if get_resume_provider() == "ollama":
                    async for sse in _ollama_stream(ENHANCE_SYSTEM_PROMPT, prompt, temperature=0.3):
                        yield sse
                else:
                    payload = {
                        "model": NVIDIA_MODEL,
                        "messages": [
                            {"role": "system", "content": ENHANCE_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 8192,
                        "temperature": 0.3,
                        "top_p": 0.95,
                        "top_k": 20,
                        "stream": True,
                    }
                    headers = {
                        "Authorization": f"Bearer {NVIDIA_API_KEY}",
                        "Accept": "text/event-stream",
                        "Content-Type": "application/json",
                    }
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        async with client.stream("POST", NVIDIA_INVOKE_URL, headers=headers, json=payload) as response:
                            if response.status_code != 200:
                                body = await response.aread()
                                logger.error(f"[RESUME ENHANCE] NVIDIA API error {response.status_code}: {body[:200]}")
                                yield f"data: {json.dumps({'error': f'NVIDIA API error: {response.status_code}'})}\n\n"
                                return
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                if line.startswith("data:"):
                                    data = line[5:].strip()
                                    if data == "[DONE]":
                                        yield "data: [DONE]\n\n"
                                        return
                                    try:
                                        chunk = json.loads(data)
                                        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                    except json.JSONDecodeError:
                                        continue
            except Exception as e:
                logger.error(f"[RESUME ENHANCE] Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            stream_enhance(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/resume/score")
    async def api_score_resume(
        request: ResumeScoreRequest,
        db: AsyncSession = Depends(get_db),
    ):
        """Score how well a resume matches a job description. Returns JSON with score breakdown."""
        if get_resume_provider() == "nvidia" and not NVIDIA_API_KEY:
            raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured. Set RESUME_PROVIDER=ollama to use local Ollama instead.")

        if not request.resume_text.strip():
            raise HTTPException(status_code=400, detail="Resume text is required")

        if request.job_id:
            result = await db.execute(select(Job).filter(Job.id == request.job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            job_description = _build_job_description(job)
        elif request.message_text:
            job_description = request.message_text.strip()
        else:
            raise HTTPException(status_code=400, detail="Either job_id or message_text is required")

        prompt = f"""请评估以下简历与职位描述的匹配度。

职位描述：
---
{job_description}
---

候选人简历：
---
{request.resume_text}
---

请输出严格的JSON格式评估结果。"""

        provider = get_resume_provider()
        logger.info(f"[RESUME SCORE] Using provider: {provider}")
        raw = ""
        try:
            if provider == "ollama":
                raw = await _ollama_complete(SCORE_SYSTEM_PROMPT, prompt, temperature=0.1)
            else:
                payload = {
                    "model": NVIDIA_MODEL,
                    "messages": [
                        {"role": "system", "content": SCORE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "stream": False,
                }
                headers = {
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)) as client:
                    response = await client.post(NVIDIA_INVOKE_URL, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    choice = data["choices"][0]
                    content = (choice.get("message") or {}).get("content") or ""
                    finish_reason = choice.get("finish_reason")
                    if not content.strip() and finish_reason == "stop":
                        logger.warning("[RESUME SCORE] NVIDIA returned empty content (content filter), returning low-score fallback")
                        return {"success": True, "result": {"score": 0, "level": "poor", "summary": "Model could not evaluate this resume.", "matched_skills": [], "missing_skills": [], "strengths": [], "improvements": []}}
                    raw = content.strip()

            raw = raw.strip("```json").strip("```").strip()
            score_data = json.loads(raw)
            return {"success": True, "result": score_data}
        except json.JSONDecodeError:
            logger.error(f"[RESUME SCORE] Failed to parse JSON from model: {raw[:300]}")
            raise HTTPException(status_code=500, detail="Model returned invalid JSON. Try again.")
        except (httpx.ReadTimeout, httpx.TimeoutException) as e:
            logger.error(f"[RESUME SCORE] Timeout calling {provider} API: {e}")
            raise HTTPException(status_code=504, detail=f"AI model ({provider}) timed out. Please try again.")
        except Exception as e:
            logger.error(f"[RESUME SCORE] Error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
