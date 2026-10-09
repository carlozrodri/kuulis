from apps.drivers.services import _type_from_extension


def test_type_from_extension() -> None:
    assert _type_from_extension("qa/drivers/u/selfie/abc-photo.JPG") == "image/jpeg"
    assert _type_from_extension("qa/drivers/u/rif/abc-doc.pdf") == "application/pdf"
    assert _type_from_extension("qa/drivers/u/rif/abc-noext") == ""
