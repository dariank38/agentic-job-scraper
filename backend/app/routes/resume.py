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
    return f"""你是一位资深的简历撰写专家和职业规划师。你的任务是根据职位描述生成专业、ATS友好的中文简历。

当前年份：{current_year}年。所有工作经历和项目的时间线必须基于此年份，最近的工作/项目截止时间应为{current_year}年（如"2022年3月 — {current_year}年6月"）。

候选人画像：
- 拥有8年以上相关工作经验
- 曾在4家以上公司任职
- 本科学历，毕业于中国排名50~200的大学
- 拥有5个以上深度参与的项目经验

简历结构（严禁包含联系方式部分）：
1. 自我评价 — 3~5句话，突出资历深度、核心竞争力和行业认知，呼应职位描述中的核心要求
2. 专业技能 — 分类列出技术栈和工具，确保覆盖职位描述中提到的关键技术、框架和方法论
3. 工作经历 — 4家以上公司，每家公司包含：
   - 公司名称（使用占位符如【公司A】）、任职时间、职位
   - 2~3条概括性工作描述，体现职责范围、业务影响和管理规模
4. 项目经历 — 5个以上项目，每个项目包含以下详细内容：
   - 项目名称（使用占位符如【项目A】）、项目时间
   - 项目背景：简要说明项目目标、业务场景和规模
   - 技术栈：列出项目中使用的核心技术、框架、中间件、工具等
   - 解决方案：详细描述技术架构设计、核心方案选型及理由、关键设计决策
   - 核心贡献：以"主导/负责/参与"开头，3~5条具量化成果的描述（如性能提升百分比、QPS提升数值、成本降低幅度、用户增长数据等）
   - 难点与亮点：1~2条技术难点及创新性解决方案
5. 教育背景 — 本科，中国排名50~200的大学（使用占位符如【大学名称】），标注专业

规则：
- 生成完整、结构清晰的中文简历（纯文本，不使用markdown格式）
- 严禁包含联系方式部分（不出现电话、邮箱、地址等）
- 使用有力的动词，尽可能量化成果和收益
- 不要编造虚假的具体公司名、大学名 — 使用占位符如【公司A】、【大学名称】等，以便求职者自行替换
- 项目经历是简历核心，每个项目必须包含详细的技术栈、解决方案、核心贡献和技术亮点
- 如果职位描述提到特定的技术、框架或方法论，必须确保在技能部分突出显示，并自然融入项目经历中
- 只输出简历文本，不要在前后添加任何评论或说明"""


def _build_prompt(job_description: str) -> str:
    return f"""请根据以下职位描述生成一份量身定制的中文简历。

职位描述：
---
{job_description}
---

要求：
- 候选人拥有8年以上经验，4家以上公司任职经历
- 本科学历，中国排名50~200大学
- 包含5个以上深度项目经历，每个项目需详细描述技术栈、解决方案、核心贡献和技术亮点
- 不要包含联系方式部分
- 使用占位符（如【公司A】、【大学名称】等）供求职者自定义
- 简历需对ATS系统友好，自然融入职位描述中的关键词"""


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
    job_id: int


class ResumeEnhanceRequest(BaseModel):
    job_id: int
    resume_text: str


class ResumeScoreRequest(BaseModel):
    job_id: int
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

        result = await db.execute(select(Job).filter(Job.id == request.job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_description = _build_job_description(job)
        if not job_description.strip():
            raise HTTPException(status_code=400, detail="Job has no description to generate resume from")

        prompt = _build_prompt(job_description)
        job_title = job.title or job.company or f"Job #{request.job_id}"
        _job_id = request.job_id

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

        result = await db.execute(select(Job).filter(Job.id == request.job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_description = _build_job_description(job)
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

        result = await db.execute(select(Job).filter(Job.id == request.job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_description = _build_job_description(job)
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
