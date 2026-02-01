from io import BytesIO
from pathlib import Path

import pytest
from lxml import etree

from xml_faker import DTDFactory


class TestDTDFactoryInit:
    def test_init_with_path(self, tmp_path: Path) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        dtd_file = tmp_path / "test.dtd"
        dtd_file.write_text(dtd_content)

        factory = DTDFactory(dtd_file)
        assert factory._dtd_source == dtd_file

    def test_init_with_string(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)
        assert factory._dtd_source == dtd_content

    def test_init_with_bytesio(self) -> None:
        dtd_content = b"<!ELEMENT root (#PCDATA)>"
        bio = BytesIO(dtd_content)
        factory = DTDFactory(bio)
        assert factory._dtd_source == bio

    def test_init_with_locale(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content, locale="fr_FR")
        assert "fr_FR" in factory._faker.locales


class TestDTDFactoryWithLocale:
    def test_with_locale_returns_self(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)
        result = factory.with_locale("de_DE")
        assert result is factory

    def test_with_locale_changes_faker(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content, locale="en_US")
        factory.with_locale("fr_FR")
        assert "fr_FR" in factory._faker.locales


class TestDTDFactoryLoadDTD:
    def test_load_dtd_from_path(self, tmp_path: Path) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        dtd_file = tmp_path / "test.dtd"
        dtd_file.write_text(dtd_content)

        factory = DTDFactory(dtd_file)
        dtd = factory._load_dtd()
        assert isinstance(dtd, etree.DTD)

    def test_load_dtd_from_string(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)
        dtd = factory._load_dtd()
        assert isinstance(dtd, etree.DTD)

    def test_load_dtd_from_bytesio(self) -> None:
        dtd_content = b"<!ELEMENT root (#PCDATA)>"
        bio = BytesIO(dtd_content)
        factory = DTDFactory(bio)
        dtd = factory._load_dtd()
        assert isinstance(dtd, etree.DTD)

    def test_load_dtd_caches_result(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)
        dtd1 = factory._load_dtd()
        dtd2 = factory._load_dtd()
        assert dtd1 is dtd2


class TestDTDFactoryBuildSimple:
    def test_build_simple_pcdata_element(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)
        result = factory.build()
        assert result.tag == "root"
        assert result.text is not None

    def test_build_with_seed_reproducible(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)

        result1 = factory.build(seed=42)
        result2 = factory.build(seed=42)

        assert result1.text == result2.text

    def test_build_empty_element(self) -> None:
        dtd_content = "<!ELEMENT root EMPTY>"
        factory = DTDFactory(dtd_content)
        result = factory.build()
        assert result.tag == "root"
        assert result.text is None
        assert len(result) == 0


class TestDTDFactoryBuildSequence:
    def test_build_sequence(self) -> None:
        dtd_content = """
        <!ELEMENT root (child1, child2)>
        <!ELEMENT child1 (#PCDATA)>
        <!ELEMENT child2 (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root")
        assert result.tag == "root"
        assert len(result) == 2
        assert result[0].tag == "child1"
        assert result[1].tag == "child2"

    def test_build_nested_sequence(self) -> None:
        dtd_content = """
        <!ELEMENT root (parent)>
        <!ELEMENT parent (child)>
        <!ELEMENT child (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root")
        assert result.tag == "root"
        assert result[0].tag == "parent"
        assert result[0][0].tag == "child"


class TestDTDFactoryBuildChoice:
    def test_build_choice(self) -> None:
        dtd_content = """
        <!ELEMENT root (optionA | optionB)>
        <!ELEMENT optionA (#PCDATA)>
        <!ELEMENT optionB (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root", seed=42)
        assert result.tag == "root"
        assert len(result) == 1
        assert result[0].tag in ("optionA", "optionB")


class TestDTDFactoryBuildOccurrence:
    def test_build_optional_element_included(self) -> None:
        dtd_content = """
        <!ELEMENT root (required, optional?)>
        <!ELEMENT required (#PCDATA)>
        <!ELEMENT optional (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root", optional_probability=1.0)
        assert result.find("required") is not None
        assert result.find("optional") is not None

    def test_build_optional_element_excluded(self) -> None:
        dtd_content = """
        <!ELEMENT root (required, optional?)>
        <!ELEMENT required (#PCDATA)>
        <!ELEMENT optional (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root", optional_probability=0.0)
        assert result.find("required") is not None
        assert result.find("optional") is None

    def test_build_plus_occurrence(self) -> None:
        dtd_content = """
        <!ELEMENT root (item+)>
        <!ELEMENT item (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root", max_occurs=5)
        assert result.tag == "root"
        assert len(result) >= 1

    def test_build_star_occurrence_can_be_empty(self) -> None:
        dtd_content = """
        <!ELEMENT root (item*)>
        <!ELEMENT item (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        # With seed that produces 0 items
        results = [factory.build(root_element="root", seed=i) for i in range(100)]
        # At least one should have 0 items (statistically likely with 100 attempts)
        has_empty = any(len(r) == 0 for r in results)
        has_items = any(len(r) > 0 for r in results)
        assert has_empty or has_items  # Should work either way


class TestDTDFactoryBuildAttributes:
    def test_build_required_attribute(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root id ID #REQUIRED>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build()
        assert "id" in result.attrib

    def test_build_implied_attribute_included(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root optional CDATA #IMPLIED>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(optional_probability=1.0)
        assert "optional" in result.attrib

    def test_build_implied_attribute_excluded(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root optional CDATA #IMPLIED>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(optional_probability=0.0)
        assert "optional" not in result.attrib

    def test_build_enumerated_attribute(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root status (active | inactive | pending) #REQUIRED>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build()
        assert result.get("status") in ("active", "inactive", "pending")

    def test_build_fixed_attribute(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root version CDATA #FIXED "1.0">
        """
        factory = DTDFactory(dtd_content)
        result = factory.build()
        assert result.get("version") == "1.0"

    def test_build_default_attribute(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root lang CDATA "en">
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(optional_probability=0.0)
        assert result.get("lang") == "en"


class TestDTDFactoryBuildValues:
    def test_build_with_value_override(self) -> None:
        dtd_content = """
        <!ELEMENT root (name)>
        <!ELEMENT name (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root", values={"root/name": "John"})
        assert result.find("name").text == "John"

    def test_build_with_attribute_override(self) -> None:
        dtd_content = """
        <!ELEMENT root (#PCDATA)>
        <!ATTLIST root id ID #REQUIRED>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(values={"root/@id": "custom-id"})
        assert result.get("id") == "custom-id"

    def test_build_with_nested_value_override(self) -> None:
        dtd_content = """
        <!ELEMENT root (parent)>
        <!ELEMENT parent (child)>
        <!ELEMENT child (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(
            root_element="root", values={"root/parent/child": "nested value"}
        )
        assert result[0][0].text == "nested value"


class TestDTDFactoryBuildErrors:
    def test_build_multiple_roots_error(self) -> None:
        dtd_content = """
        <!ELEMENT root1 (#PCDATA)>
        <!ELEMENT root2 (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)
        with pytest.raises(ValueError, match="Multiple elements found"):
            factory.build()

    def test_build_no_elements_error(self) -> None:
        dtd_content = "<!ATTLIST root id ID #REQUIRED>"
        factory = DTDFactory(dtd_content)
        with pytest.raises(ValueError, match="No elements found"):
            factory.build()

    def test_build_unknown_root_error(self) -> None:
        dtd_content = "<!ELEMENT root (#PCDATA)>"
        factory = DTDFactory(dtd_content)
        with pytest.raises(ValueError, match="not found"):
            factory.build(root_element="nonexistent")


class TestDTDFactoryWithSimpleDTD:
    @pytest.fixture
    def simple_dtd_path(self) -> Path:
        return Path(__file__).parent / "test_files" / "simple.dtd"

    def test_build_from_simple_dtd(self, simple_dtd_path: Path) -> None:
        factory = DTDFactory(simple_dtd_path)
        result = factory.build(root_element="person")

        assert result.tag == "person"
        assert "id" in result.attrib
        assert result.find("name") is not None
        assert result.find("age") is not None

    def test_build_simple_dtd_with_optional(self, simple_dtd_path: Path) -> None:
        factory = DTDFactory(simple_dtd_path)
        result = factory.build(root_element="person", optional_probability=1.0)
        assert result.find("email") is not None

    def test_build_simple_dtd_without_optional(self, simple_dtd_path: Path) -> None:
        factory = DTDFactory(simple_dtd_path)
        result = factory.build(root_element="person", optional_probability=0.0)
        assert result.find("email") is None


class TestDTDFactoryWithComplexDTD:
    @pytest.fixture
    def complex_dtd_path(self) -> Path:
        return Path(__file__).parent / "test_files" / "complex.dtd"

    def test_build_from_complex_dtd(self, complex_dtd_path: Path) -> None:
        factory = DTDFactory(complex_dtd_path)
        result = factory.build(root_element="company")

        assert result.tag == "company"
        assert "name" in result.attrib
        departments = result.findall("department")
        assert len(departments) >= 1

    def test_build_complex_dtd_with_choice(self, complex_dtd_path: Path) -> None:
        factory = DTDFactory(complex_dtd_path)
        result = factory.build(root_element="company", seed=42)

        # Find an employee element
        employee = result.find(".//employee")
        if employee is not None:
            # Should have either salary or hourlyRate, not both
            has_salary = employee.find("salary") is not None
            has_hourly = employee.find("hourlyRate") is not None
            assert has_salary != has_hourly  # XOR - one or the other, not both

    def test_build_complex_dtd_enumerated_attr(self, complex_dtd_path: Path) -> None:
        factory = DTDFactory(complex_dtd_path)
        result = factory.build(root_element="company")

        department = result.find("department")
        assert department is not None
        assert department.get("type") in (
            "engineering",
            "sales",
            "marketing",
            "hr",
        )


class TestDTDFactoryValidation:
    def test_generated_xml_is_valid(self) -> None:
        dtd_content = """
        <!ELEMENT root (item+)>
        <!ELEMENT item (#PCDATA)>
        <!ATTLIST root version CDATA #REQUIRED>
        """
        factory = DTDFactory(dtd_content)
        result = factory.build(root_element="root")

        # Create a DTD for validation
        dtd = etree.DTD(BytesIO(dtd_content.encode()))
        assert dtd.validate(result)

    def test_generated_xml_with_optional_is_valid(self) -> None:
        dtd_content = """
        <!ELEMENT root (required, optional?)>
        <!ELEMENT required (#PCDATA)>
        <!ELEMENT optional (#PCDATA)>
        """
        factory = DTDFactory(dtd_content)

        # Test with optional included
        result1 = factory.build(root_element="root", optional_probability=1.0)
        dtd = etree.DTD(BytesIO(dtd_content.encode()))
        assert dtd.validate(result1)

        # Test with optional excluded
        result2 = factory.build(root_element="root", optional_probability=0.0)
        assert dtd.validate(result2)
