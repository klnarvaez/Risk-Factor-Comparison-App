from llm_adapter import LLMAdapter


def test_cache_prevents_duplicate_calls():
    adapter = LLMAdapter(mode="mock")
    assert adapter.api_call_count == 0
    r1 = adapter.get_company_risks("Acme Inc", top_n=3)
    assert adapter.api_call_count == 1
    r2 = adapter.get_company_risks("acme inc", top_n=3)
    # case-insensitive key should reuse the cache
    assert adapter.api_call_count == 1
    assert r1 == r2

    # clearing cache causes a new call
    adapter.clear_cache()
    r3 = adapter.get_company_risks("ACME INC", top_n=3)
    assert adapter.api_call_count == 2


def test_cache_respects_top_n():
    adapter = LLMAdapter(mode="mock")
    adapter.clear_cache()
    adapter.get_company_risks("Beta Corp", top_n=3)
    assert adapter.api_call_count == 1
    # different top_n should cause new call
    adapter.get_company_risks("Beta Corp", top_n=2)
    assert adapter.api_call_count == 2
