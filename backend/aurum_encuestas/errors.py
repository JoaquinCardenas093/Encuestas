class AurumError(Exception):
    """Base for typed app errors."""
    code: str = "internal_error"
    status: int = 500


class XlsxParseError(AurumError):
    code = "xlsx_parse_error"
    status = 400


class TemplateInvalidError(AurumError):
    code = "template_invalid"
    status = 400


class ProjectIOError(AurumError):
    code = "project_io_error"
    status = 500


class LLMError(AurumError):
    code = "llm_error"
    status = 502


class RenderError(AurumError):
    code = "render_error"
    status = 500
