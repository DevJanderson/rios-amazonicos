"""HTTP download shared by all sources: identified User-Agent, timeout, raw response."""

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

USER_AGENT = "rios-amazonicos/0.1 (+https://github.com/DevJanderson/rios-amazonicos)"
TIMEOUT_SECONDS = 90.0


@dataclass(frozen=True)
class Resposta:
    url: str
    status_http: int
    conteudo: bytes
    recebido_em: datetime

    @property
    def ok(self) -> bool:
        return self.status_http == 200


def baixar(url: str, client: httpx.Client | None = None) -> Resposta:
    """Download a URL once. Network errors propagate; HTTP errors are returned."""
    if client is None:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS) as c:
            return baixar(url, c)
    r = client.get(url, follow_redirects=True)
    return Resposta(
        url=str(r.url),
        status_http=r.status_code,
        conteudo=r.content,
        recebido_em=datetime.now(UTC),
    )
