__all__ = ["IExplainService"]


def __getattr__(name: str):
    if name == "IExplainService":
        from iexplain.runtime.service import IExplainService

        return IExplainService
    raise AttributeError(name)
