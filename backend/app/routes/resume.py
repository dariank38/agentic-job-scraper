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
from sqlalchemy.orm import selectinload

from app.connection import get_db, manager
from app.models import Job, Resume
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
        "You are a senior professional resume writer. Create a detailed Chinese resume for a job candidate.\n\n"
        f"CRITICAL: Current year is {current_year}. All dates must end in {current_year}. "
        f"Do NOT use dates from job description - they may be outdated.\n\n"
        "CANDIDATE PROFILE:\n"
        "- 8 years experience, 4 companies (1 famous Chinese IT giant: ByteDance/Huawei/Xiaomi/JD/NetEase/Meituan/Didi/Bilibili/Kuaishou/Pinduoduo/OPPO/Lenovo, 3 mid-sized real companies)\n"
        "- MUST have at least 12 projects total (3-4 per company, never fewer than 3 per company)\n"
        "- Bachelor's from real Chinese university ranked 50-150\n\n"
        "RESUME STRUCTURE (output ONLY these sections in order):\n"
        "1. 个人简介: 5-12 sentences (~250-350 chars), covering experience, strengths, expertise, alignment with job\n"
        "2. 专业技能: Categorized list of all key technologies from job description with proficiency notes\n"
        "3. 工作经历: 4 companies. Each: company name, period, title, tech stack, 6-8 detailed bullets (responsibilities, decisions, problems/solutions, impact, quantified results)\n"
        "4. 项目经历: At least 12 projects (3-4 per company). Each: name, period, background (goal/context/scale/challenges), tech stack, PROBLEMS & SOLUTIONS (detailed: specific technical issues, investigation process, root cause, implementation, outcome), 6-8 contribution bullets with quantified results\n"
        "5. 教育背景: Bachelor's, real university 50-150, major, graduation year, 2-3 courses\n\n"
        "STRICT RULES:\n"
        "- Output ONLY resume text, no preamble/commentary\n"
        "- NO contact info, NO 附加信息/兴趣爱好/证书/自我评价\n"
        "- Plain text only, no markdown\n"
        "- Real company/university/project names only, no placeholders\n"
        f"- Timeline consistent: projects within company tenure, no overlap, 8 years ending in {current_year}\n"
        "- Use strong action verbs, quantify achievements\n"
        "- Integrate job description keywords naturally"
    )


def _build_prompt(job_description: str) -> str:
    current_year = datetime.datetime.now().year
    return (
        f"Create a detailed Chinese resume for this job:\n\n"
        f"Job Description:\n---\n{job_description}\n---\n\n"
        f"Requirements:\n"
        f"- CRITICAL: Ignore job description dates. Use {current_year} as current year.\n"
        f"- 8 years experience, 4 companies (1 famous Chinese IT giant, 3 mid-sized real companies), at least 12 projects (3-4 per company), ending in {current_year}\n"
        f"- Work entries: tech stack, responsibilities, decisions, problems/solutions, impact, team size, quantified results\n"
        f"- Project entries: background, tech stack, DETAILED PROBLEMS & SOLUTIONS (specific issues, investigation, root cause, implementation, outcome), quantified contributions\n"
        f"- Real Chinese university 50-150, real company/university/project names only\n"
        f"- Timeline consistent, no overlaps, projects within company tenure\n"
        f"- Output ONLY resume text"
    )


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
  "strengths": ["<优势1>", "<优势2>"],
  "improvements": ["<建议1>", "<建议2>"]
}

字段说明：
- score：0-100的整数
- level：必须是 "excellent"、"good"、"fair"、"poor" 四者之一（英文小写，不要翻译）
- summary：1个字符串，2-3句话的总体评价
- matched_skills / missing_skills：字符串数组，2-6项
- strengths / improvements：字符串数组，2-4项

【评分标准】
- 90-100：技能高度吻合，经验完全匹配
- 70-89：大部分要求满足，少数缺口
- 50-69：部分匹配，有明显技能缺口
- 0-49：匹配度低，需大量补充

再次提醒：只输出符合上述结构的JSON对象本身，不要输出其他任何文字。"""


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
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,        # avoid silent prompt truncation
            "num_predict": 4096,    # enough room for a full resume
            "top_p": 0.95,
            "top_k": 20,
            "repeat_penalty": 1.1,
        },
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
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,
        },
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
            result = await db.execute(select(Job).options(selectinload(Job.message)).filter(Job.id == request.job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            # Use message text if available, otherwise build from structured fields
            if job.message and job.message.text:
                job_description = job.message.text
            else:
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
                job_description = "\n".join(parts)
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

        # Log prompt lengths for debugging
        system_prompt = _get_system_prompt()
        system_len = len(system_prompt)
        user_len = len(prompt)
        total_len = system_len + user_len
        # Rough token estimate: ~1.5 chars per token for Chinese
        estimated_tokens = int(total_len / 1.5)
        logger.info(f"[RESUME GENERATE] job_id={_job_id} | system_prompt={system_len} chars | user_prompt={user_len} chars | total={total_len} chars | estimated_tokens={estimated_tokens}")

        async def stream_resume():
            await manager.broadcast({"type": "resume_generating", "job_id": _job_id, "job_title": job_title})
            full_content = ""
            try:
                if get_resume_provider() == "ollama":
                    async for sse in _ollama_stream(_get_system_prompt(), prompt, temperature=0.4):
                        yield sse
                        # Extract content from SSE for saving
                        if sse.startswith("data: {"):
                            try:
                                data = json.loads(sse[5:])
                                if "content" in data:
                                    full_content += data["content"]
                            except json.JSONDecodeError:
                                pass
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
                                            full_content += content
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                    except json.JSONDecodeError:
                                        continue
            except Exception as e:
                logger.error(f"[RESUME] Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                await manager.broadcast({"type": "resume_complete", "job_id": _job_id})

                # Save resume to database
                if full_content.strip():
                    try:
                        new_resume = Resume(
                            job_id=request.job_id if request.job_id else None,
                            job_title=job_title,
                            job_company=job.company if request.job_id and job else None,
                            resume_type="generate",
                            content=full_content.strip()
                        )
                        db.add(new_resume)
                        await db.commit()
                        logger.info(f"[RESUME] Saved generated resume id={new_resume.id}")
                    except Exception as e:
                        logger.error(f"[RESUME] Failed to save resume: {e}")
                        await db.rollback()

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
            result = await db.execute(select(Job).options(selectinload(Job.message)).filter(Job.id == request.job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            # Use message text if available, otherwise build from structured fields
            if job.message and job.message.text:
                job_description = job.message.text
            else:
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
                job_description = "\n".join(parts)
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

        # Log prompt lengths for debugging
        system_len = len(ENHANCE_SYSTEM_PROMPT)
        user_len = len(prompt)
        resume_len = len(request.resume_text)
        total_len = system_len + user_len
        estimated_tokens = int(total_len / 1.5)
        logger.info(f"[RESUME ENHANCE] job_id={request.job_id} | system_prompt={system_len} chars | user_prompt={user_len} chars | resume_text={resume_len} chars | total={total_len} chars | estimated_tokens={estimated_tokens}")

        async def stream_enhance():
            full_content = ""
            try:
                if get_resume_provider() == "ollama":
                    async for sse in _ollama_stream(ENHANCE_SYSTEM_PROMPT, prompt, temperature=0.3):
                        yield sse
                        # Extract content from SSE for saving
                        if sse.startswith("data: {"):
                            try:
                                data = json.loads(sse[5:])
                                if "content" in data:
                                    full_content += data["content"]
                            except json.JSONDecodeError:
                                pass
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
                                            full_content += content
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                    except json.JSONDecodeError:
                                        continue
            except Exception as e:
                logger.error(f"[RESUME ENHANCE] Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                # Save resume to database
                if full_content.strip():
                    try:
                        job_title = job.title if request.job_id and job else "Enhanced Resume"
                        job_company = job.company if request.job_id and job else None
                        new_resume = Resume(
                            job_id=request.job_id if request.job_id else None,
                            job_title=job_title,
                            job_company=job_company,
                            resume_type="enhance",
                            content=full_content.strip()
                        )
                        db.add(new_resume)
                        await db.commit()
                        logger.info(f"[RESUME] Saved enhanced resume id={new_resume.id}")
                    except Exception as e:
                        logger.error(f"[RESUME] Failed to save resume: {e}")
                        await db.rollback()

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
            result = await db.execute(select(Job).options(selectinload(Job.message)).filter(Job.id == request.job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            # Use message text if available, otherwise build from structured fields
            if job.message and job.message.text:
                job_description = job.message.text
            else:
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
                job_description = "\n".join(parts)
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

            # Save score result to database
            try:
                job_title = job.title if request.job_id and job else "Scored Resume"
                job_company = job.company if request.job_id and job else None
                new_resume = Resume(
                    job_id=request.job_id if request.job_id else None,
                    job_title=job_title,
                    job_company=job_company,
                    resume_type="score",
                    content=request.resume_text,
                    score_result=score_data
                )
                db.add(new_resume)
                await db.commit()
                logger.info(f"[RESUME] Saved scored resume id={new_resume.id}")
            except Exception as e:
                logger.error(f"[RESUME] Failed to save resume: {e}")
                await db.rollback()

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

    @app.get("/api/resumes")
    async def api_list_resumes(
        resume_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """List all generated resumes with optional filtering by type."""
        query = select(Resume).order_by(Resume.created_at.desc())
        if resume_type:
            query = query.filter(Resume.resume_type == resume_type)
        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        resumes = result.scalars().all()
        return {"resumes": [r.to_dict() for r in resumes]}

    @app.get("/api/resumes/{resume_id}")
    async def api_get_resume(
        resume_id: int,
        db: AsyncSession = Depends(get_db),
    ):
        """Get a specific resume by ID."""
        result = await db.execute(select(Resume).filter(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        return resume.to_dict()

    @app.delete("/api/resumes/{resume_id}")
    async def api_delete_resume(
        resume_id: int,
        db: AsyncSession = Depends(get_db),
    ):
        """Delete a specific resume by ID."""
        result = await db.execute(select(Resume).filter(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        await db.delete(resume)
        await db.commit()
        return {"success": True, "message": "Resume deleted"}
