import pytest

from cat.mad_hatter.mad_hatter import MadHatter
from cat.services.model_providers.default import DefaultModelProvider


@pytest.fixture(scope="function")
def cheshire_cat(client):
    yield client.app.state.ccat


def test_main_modules_loaded(cheshire_cat):
    assert isinstance(
        cheshire_cat.mad_hatter, MadHatter
    )


@pytest.mark.asyncio
async def test_default_provider_loaded(cheshire_cat):
    provider = await cheshire_cat.factory.get("model_providers", "default")
    assert isinstance(provider, DefaultModelProvider)
    assert provider.list_llms() == ["default"]
