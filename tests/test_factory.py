from io import BytesIO
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from lxml import etree

from xml_faker import XMLFactory

TEST_FILES = Path(__file__).parent / "test_files"
XHTML_STRICT_XSD = TEST_FILES / "xhtml1-strict.xsd"
SIMPLE_XSD = TEST_FILES / "simple.xsd"
COMPLEX_XSD = TEST_FILES / "complex.xsd"


class TestXMLFactoryInit:
    def test_init_with_path(self):
        factory = XMLFactory(SIMPLE_XSD)
        assert factory._schema_source == SIMPLE_XSD

    def test_init_with_string(self):
        schema_content = SIMPLE_XSD.read_text()
        factory = XMLFactory(schema_content)
        assert factory._schema_source == schema_content

    def test_init_with_bytesio(self):
        schema_bytes = SIMPLE_XSD.read_bytes()
        bio = BytesIO(schema_bytes)
        factory = XMLFactory(bio)
        assert factory._schema_source is bio

    def test_init_with_locale(self):
        factory = XMLFactory(SIMPLE_XSD, locale="fr_FR")
        assert factory._faker.locales == ["fr_FR"]

    def test_init_with_multiple_locales(self):
        factory = XMLFactory(SIMPLE_XSD, locale=["fr_FR", "en_US"])
        assert factory._faker.locales == ["fr_FR", "en_US"]

    def test_init_with_xhtml_strict_xsd(self):
        factory = XMLFactory(XHTML_STRICT_XSD)
        assert factory._schema_source == XHTML_STRICT_XSD


class TestXMLFactoryWithLocale:
    def test_with_locale_changes_faker(self):
        factory = XMLFactory(SIMPLE_XSD, locale="en_US")
        factory.with_locale("de_DE")
        assert factory._faker.locales == ["de_DE"]

    def test_with_locale_returns_self(self):
        factory = XMLFactory(SIMPLE_XSD)
        result = factory.with_locale("fr_FR")
        assert result is factory


class TestXMLFactoryLoadSchema:
    def test_load_schema_from_path(self):
        factory = XMLFactory(SIMPLE_XSD)
        schema = factory._load_schema()
        assert schema is not None

    def test_load_schema_from_string(self):
        schema_content = SIMPLE_XSD.read_text()
        factory = XMLFactory(schema_content)
        schema = factory._load_schema()
        assert schema is not None

    def test_load_schema_from_bytesio(self):
        schema_bytes = SIMPLE_XSD.read_bytes()
        bio = BytesIO(schema_bytes)
        factory = XMLFactory(bio)
        schema = factory._load_schema()
        assert schema is not None

    def test_load_schema_caches_result(self):
        factory = XMLFactory(SIMPLE_XSD)
        schema1 = factory._load_schema()
        schema2 = factory._load_schema()
        assert schema1 is schema2

    @pytest.mark.skip(reason="XHTML schema requires external xml namespace resolution")
    def test_load_xhtml_strict_schema(self):
        factory = XMLFactory(XHTML_STRICT_XSD)
        schema = factory._load_schema()
        assert schema is not None


class TestXMLFactoryBuild:
    def test_build_returns_element(self):
        factory = XMLFactory(SIMPLE_XSD)
        result = factory.build()
        assert isinstance(result, etree._Element)

    def test_build_returns_valid_xml(self):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build()
        assert root.tag == "person"

    def test_build_includes_required_elements(self):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build()
        assert root.find("name") is not None
        assert root.find("age") is not None

    def test_build_includes_required_attributes(self):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build()
        assert "id" in root.attrib

    def test_build_with_seed_is_reproducible(self):
        factory = XMLFactory(SIMPLE_XSD)
        result1 = factory.build(seed=42)
        result2 = factory.build(seed=42)
        assert etree.tostring(result1) == etree.tostring(result2)

    def test_build_with_different_seeds_differs(self):
        factory = XMLFactory(SIMPLE_XSD)
        result1 = factory.build(seed=42)
        result2 = factory.build(seed=123)
        assert etree.tostring(result1) != etree.tostring(result2)

    def test_build_with_values_override(self):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build(
            values={"person/name": "John Doe", "person/@id": "custom-id"}
        )
        assert root.find("name").text == "John Doe"
        assert root.get("id") == "custom-id"

    def test_build_with_optional_probability_zero(self):
        factory = XMLFactory(SIMPLE_XSD)
        # email is optional (minOccurs=0), with probability 0 it should not appear
        root = factory.build(optional_probability=0.0, seed=42)
        assert root.find("email") is None

    def test_build_with_optional_probability_one(self):
        factory = XMLFactory(SIMPLE_XSD)
        # email is optional, with probability 1 it should appear
        root = factory.build(optional_probability=1.0, seed=42)
        assert root.find("email") is not None

    def test_build_can_be_serialized(self):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build()
        xml_bytes = etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        )
        assert isinstance(xml_bytes, bytes)
        assert b"<person" in xml_bytes


class TestXMLFactoryComplex:
    def test_build_complex_schema(self):
        factory = XMLFactory(COMPLEX_XSD)
        root = factory.build(seed=42)
        assert root.tag == "company"
        assert root.find("name") is not None
        assert root.find("employees") is not None

    def test_build_respects_max_occurs(self):
        factory = XMLFactory(COMPLEX_XSD)
        root = factory.build(max_occurs=2, seed=42)
        employees = root.findall(".//employee")
        assert len(employees) <= 2

    def test_build_enumeration_values(self):
        factory = XMLFactory(COMPLEX_XSD)
        # Run multiple times to check enumeration is respected
        valid_statuses = {"active", "inactive", "pending"}
        for seed in range(10):
            root = factory.build(seed=seed)
            status = root.find(".//status")
            assert status is not None
            assert status.text in valid_statuses

    def test_build_numeric_constraints(self):
        factory = XMLFactory(COMPLEX_XSD)
        for seed in range(10):
            root = factory.build(seed=seed)
            age = root.find(".//age")
            assert age is not None
            age_val = int(age.text)
            assert 0 <= age_val <= 150

    def test_build_choice_picks_one(self):
        factory = XMLFactory(COMPLEX_XSD)
        root = factory.build(seed=42)
        employee = root.find(".//employee")
        salary = employee.find("salary")
        hourly_rate = employee.find("hourlyRate")
        # Exactly one should be present
        assert (salary is not None) != (hourly_rate is not None)


class TestXMLFactoryErrors:
    def test_build_with_invalid_root_element(self):
        factory = XMLFactory(SIMPLE_XSD)
        with pytest.raises(ValueError, match="not found"):
            factory.build(root_element="nonexistent")

    def test_build_multiple_roots_requires_specification(self):
        schema = """<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
          <xs:element name="foo" type="xs:string"/>
          <xs:element name="bar" type="xs:string"/>
        </xs:schema>
        """
        factory = XMLFactory(schema)
        with pytest.raises(ValueError, match="Multiple root elements"):
            factory.build()

    def test_build_multiple_roots_with_specification(self):
        schema = """<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
          <xs:element name="foo" type="xs:string"/>
          <xs:element name="bar" type="xs:string"/>
        </xs:schema>
        """
        factory = XMLFactory(schema)
        root = factory.build(root_element="foo")
        assert root.tag == "foo"


class TestXMLFactoryHypothesis:
    @given(locale=st.sampled_from(["en_US", "fr_FR", "de_DE", "es_ES", "it_IT"]))
    def test_init_with_various_locales(self, locale: str):
        factory = XMLFactory(SIMPLE_XSD, locale=locale)
        assert factory._faker.locales == [locale]

    @given(seed=st.integers(min_value=0, max_value=10000))
    def test_build_with_random_seeds(self, seed: int):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build(seed=seed)
        assert root.tag == "person"
        assert root.find("name") is not None

    @given(
        optional_probability=st.floats(min_value=0.0, max_value=1.0),
        max_occurs=st.integers(min_value=1, max_value=10),
    )
    def test_build_with_various_parameters(
        self, optional_probability: float, max_occurs: int
    ):
        factory = XMLFactory(SIMPLE_XSD)
        root = factory.build(
            optional_probability=optional_probability,
            max_occurs=max_occurs,
            seed=42,
        )
        assert root.tag == "person"
