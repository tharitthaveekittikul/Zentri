from app.services.hardware import detect_hardware, HardwareInfo


def test_detect_hardware_returns_hardware_info():
    info = detect_hardware()
    assert isinstance(info, HardwareInfo)
    assert info.cpu_brand != ""
    assert info.ram_gb > 0


def test_recommendation_provided():
    info = detect_hardware()
    rec = info.recommendation
    assert rec["recommended_model"] != ""
    assert "note" in rec
    assert isinstance(rec["can_run_local_llm"], bool)
    assert "setup_command" in rec
