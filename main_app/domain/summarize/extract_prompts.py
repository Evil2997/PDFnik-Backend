EXTRACT_PROMPTS: dict[str, str | None] = {
    "summary": (
        "Summarize the following transcript clearly and concisely in English. "
        "Cover the main topics, key points, and conclusions. Keep it under 400 words.\n\n{text}"
    ),
    "learn": (
        "You are an expert teacher. From the transcript below, extract:\n"
        "1. Core concepts and their definitions\n"
        "2. Mental models or frameworks introduced\n"
        "3. A suggested learning path\n\n"
        "Write in English with clear section headers.\n\nTranscript:\n{text}"
    ),
    "commands": (
        "You are a technical writer. From the transcript below, extract ALL:\n"
        "- CLI commands and flags\n"
        "- Code snippets\n"
        "- File names and paths\n"
        "- Configuration examples\n\n"
        "Format as a clean reference list. If nothing technical is found, say so.\n\nTranscript:\n{text}"
    ),
    "pipeline": (
        "You are a process analyst. From the transcript below, extract all workflows, "
        "processes, and procedures. Format as numbered step-by-step instructions "
        "with clear action verbs.\n\nTranscript:\n{text}"
    ),
    "tips": (
        "You are a practical advisor. From the transcript below, extract all actionable tips, "
        "best practices, non-obvious advice, and pro tips. "
        "Format as a concise bullet list.\n\nTranscript:\n{text}"
    ),
    "none": None,
}

MODE_LABELS: dict[str, str] = {
    "summary": "Summary",
    "learn": "Key Concepts & Learning Path",
    "commands": "Commands & Code",
    "pipeline": "Step-by-Step Pipeline",
    "tips": "Practical Tips",
    "none": "Transcript",
}

DEFAULT_MODE = "summary"
