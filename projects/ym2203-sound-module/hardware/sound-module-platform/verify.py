"""Check the pin-budget proposal. Does not validate electrical timing or firmware."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    d = json.loads((ROOT / "design.json").read_text())
    gpio, connector, profiles = d["gpio"], d["connector"], d["profiles"]
    exposed = set(range(23)) | {26, 27, 28}
    assert len(gpio) == len(exposed) == 26
    assert {x["gpio"] for x in gpio} == exposed
    assert len({x["signal"] for x in gpio}) == 26
    assert len({x["pico_physical_pin"] for x in gpio}) == 26
    by_signal = {x["signal"]: x["gpio"] for x in gpio}
    assert [by_signal[f"D{i}"] for i in range(8)] == list(range(8))
    assert (by_signal["HOST_SDA"], by_signal["HOST_SCL"]) == (20, 21)
    assert (by_signal["AUX_SDA"], by_signal["AUX_SCL"]) == (26, 27)
    # RP2350 peripheral function table: SDA pair %4=0 -> I2C0, %4=2 -> I2C1.
    assert by_signal["HOST_SDA"] % 4 == 0
    assert by_signal["AUX_SDA"] % 4 == 2
    assert by_signal["I2S_LRCK"] == by_signal["I2S_BCLK"] + 1
    assert len(connector) == 50
    assert [x["pin"] for x in connector] == list(range(1, 51))
    special = {"GND", "AGND", "+5V"}
    names = [x["signal"] for x in connector if x["signal"] not in special]
    assert len(names) == len(set(names))
    for x in connector:
        if x["source"].startswith("GP"):
            assert by_signal[x["signal"]] == int(x["source"][2:])
        if x["direction"] not in {"reference", "unconnected"} and not x["signal"].startswith(("ANALOG_", "+")):
            assert x["voltage"] == "3.3V"
    assert connector[-1]["signal"] == "KEY_NC"
    assert {p["chip"] for p in profiles} == {"YM2203C", "YM2608", "YM2610", "SN76489AN", "YMZ285", "YMZ294"}
    assert {p["board_id"] for p in profiles} == set(range(1, 7))
    module_names = {x["signal"] for x in connector}
    for p in profiles:
        assert set(p["required"]) <= module_names, p["chip"]
        if "stereo" in p["digital"]:
            assert {"FM_SD", "FM_CLK", "FM_SH1", "FM_SH2"} <= set(p["required"])
        if not p["readable"]:
            assert "RD_N" not in p["required"]
    exp = d["expander"]
    assert len({x["pin"] for x in exp}) == len(exp) == 16
    # Current MCP23017 revisions may make port bit 7 output-only.
    assert all(x["direction"] == "output" for x in exp if x["pin"] in {"GPA7", "GPB7"})
    assert not ({f"D{i}" for i in range(8)} | {"CS_N", "WR_N", "RD_N", "STATUS", "FM_CLK"}) & {x["signal"] for x in exp}
    assert not d["hot_swap"] and d["memory_realtime_on_module"] and not d["mclk_from_pico"]
    assert d["pio_budget"]["planned_blocks"] <= d["pio_budget"]["available_blocks"]
    assert d["pio_budget"]["dma_channels_planned"] <= d["pio_budget"]["dma_channels_available"]
    for filename, rows in [("gpio.csv", gpio), ("connector.csv", connector), ("expander.csv", exp)]:
        with (ROOT / filename).open(newline="", encoding="utf-8") as f:
            actual = list(csv.DictReader(f))
        expected = [{k: str(v) for k, v in row.items()} for row in rows]
        assert actual == expected, filename
    report = dict(
        revision=d["revision"], result="pass", gpio_used=26, gpio_available=26,
        connector_contacts=50, expander_io=16, profiles_checked=6,
        checks=["unique exposed GPIO and physical pins", "I2C0/I2C1 pin functions",
                "consecutive I2S clock pins", "six profile signal coverage",
                "connector digital voltage contract", "expander port-7 direction",
                "CSV/JSON agreement", "PIO/DMA resource budget"],
        not_verified=["schematic/ERC", "PCB signal integrity", "reset transient timing",
                      "native IC package pin-to-pin wiring", "memory bridge and loader",
                      "PIO assembled code and instruction-memory fit", "real-time simultaneous throughput",
                      "sound output and long-duration playback", "actual stock at ordering time"],
    )
    (ROOT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
