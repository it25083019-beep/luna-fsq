from name_utils import extract_display_name, is_valid_display_name, sanitize_display_name


def test_spanish_intro():
    assert extract_display_name("Me llamo Paula") == "Paula"
    print("OK spanish", extract_display_name("Me llamo Paula"))


def test_japanese_intro():
    assert extract_display_name("僕の名前は、井田") == "井田"
    assert extract_display_name("私は太郎です") == "太郎"
    print("OK japanese")


def test_reject_consult_phrase():
    assert sanitize_display_name("体調を相談したい") == ""
    assert sanitize_display_name("お金の相談") == ""
    print("OK reject consult")


def test_short_name_ok():
    assert is_valid_display_name("Pau")
    assert is_valid_display_name("井田")
    print("OK short names")


if __name__ == "__main__":
    test_spanish_intro()
    test_japanese_intro()
    test_reject_consult_phrase()
    test_short_name_ok()
    print("ALL name_utils tests OK")
