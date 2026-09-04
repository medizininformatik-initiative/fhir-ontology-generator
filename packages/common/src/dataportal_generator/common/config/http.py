from pydantic import BaseModel


class SSLConfig(BaseModel):
    public: str
    private: str