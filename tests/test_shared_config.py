from shared_config import SharedConfig


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"{}"


def test_download_from_api_encodes_params_without_mutating_api_url(monkeypatch):
    api_url = "https://example.test/config?source=bot"
    monkeypatch.setattr(SharedConfig, "API_URL", api_url)
    requested_urls = []

    def fake_urlopen(url, timeout):
        requested_urls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr("shared_config.request.urlopen", fake_urlopen)

    SharedConfig._download_from_api({"text": "媒体传送失败"})
    SharedConfig._download_from_api()

    assert requested_urls == [
        (
            "https://example.test/config?source=bot&"
            "text=%E5%AA%92%E4%BD%93%E4%BC%A0%E9%80%81%E5%A4%B1%E8%B4%A5",
            10,
        ),
        (api_url, 10),
    ]
    assert SharedConfig.API_URL == api_url
