from __future__ import annotations

from io import BytesIO
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Any, Self

from faker import Faker
from lxml import etree

if TYPE_CHECKING:
    from lxml.etree import _DTDAttributeDecl, _DTDElementContent, _DTDElementDecl


class DTDFactory:
    """Factory for generating fake XML data from DTD (Document Type Definition) files."""

    def __init__(
        self,
        dtd: BytesIO | str | Path,
        *,
        locale: str | list[str] | None = None,
    ) -> None:
        self._dtd_source = dtd
        self._dtd: etree.DTD | None = None
        self._faker = Faker(locale)
        self._random = Random()

    def _load_dtd(self) -> etree.DTD:
        if self._dtd is not None:
            return self._dtd

        match self._dtd_source:
            case BytesIO() as bio:
                bio.seek(0)
                self._dtd = etree.DTD(bio)
            case Path() as path:
                self._dtd = etree.DTD(str(path))
            case str() as content:
                bio = BytesIO(content.encode())
                self._dtd = etree.DTD(bio)

        assert self._dtd is not None
        return self._dtd

    def with_locale(self, locale: str | list[str]) -> Self:
        self._faker = Faker(locale)
        return self

    def _find_root_elements(self) -> list[str]:
        """Find potential root elements in the DTD.

        Since DTDs don't explicitly declare root elements, we return all defined elements.
        Elements that are referenced by other elements but still could be roots.
        """
        dtd = self._load_dtd()
        elements = []
        for elem in dtd.iterelements():
            elements.append(elem.name)
        return elements

    def _find_element_by_name(self, name: str) -> _DTDElementDecl | None:
        dtd = self._load_dtd()
        for elem in dtd.iterelements():
            if elem.name == name:
                return elem
        return None

    def _should_include_optional(self, optional_probability: float) -> bool:
        return self._random.random() < optional_probability

    def _generate_pcdata(self) -> str:
        """Generate text content for #PCDATA."""
        return self._faker.sentence()

    def _generate_attribute_value(
        self, attr: _DTDAttributeDecl, values: dict[str, Any] | None, path: str
    ) -> str | None:
        """Generate a value for an attribute based on its declaration."""
        attr_path = f"{path}/@{attr.name}"

        # Check for override value
        if values and attr_path in values:
            return str(values[attr_path])

        # Handle different attribute types
        match attr.type:
            case "cdata":
                return self._faker.word()
            case "id":
                return self._faker.uuid4()[:8]
            case "idref" | "idrefs":
                return self._faker.uuid4()[:8]
            case "nmtoken":
                return self._faker.word()
            case "nmtokens":
                return " ".join(self._faker.words(nb=self._random.randint(1, 3)))
            case "entity" | "entities":
                return self._faker.word()
            case "enumeration":
                # Choose from enumerated values
                if attr.values():
                    return self._random.choice(list(attr.values()))
                return self._faker.word()
            case _:
                return self._faker.word()

    def _build_attributes(
        self,
        element: etree._Element,
        element_decl: _DTDElementDecl,
        values: dict[str, Any] | None,
        optional_probability: float,
        path: str,
    ) -> None:
        """Build attributes for an element based on DTD declarations."""
        for attr in element_decl.iterattributes():
            attr_path = f"{path}/@{attr.name}"

            # Check for override value first
            if values and attr_path in values:
                element.set(attr.name, str(values[attr_path]))
                continue

            # Determine if we should include this attribute
            match attr.default:
                case "required":
                    # Must include
                    value = self._generate_attribute_value(attr, values, path)
                    if value is not None:
                        element.set(attr.name, value)
                case "implied":
                    # Optional
                    if self._should_include_optional(optional_probability):
                        value = self._generate_attribute_value(attr, values, path)
                        if value is not None:
                            element.set(attr.name, value)
                case "fixed":
                    # Fixed value - use the default value
                    if attr.default_value is not None:
                        element.set(attr.name, attr.default_value)
                case _:
                    # Has a default value, optionally override
                    if self._should_include_optional(optional_probability):
                        value = self._generate_attribute_value(attr, values, path)
                        if value is not None:
                            element.set(attr.name, value)
                    elif attr.default_value is not None:
                        element.set(attr.name, attr.default_value)

    def _build_element(
        self,
        element_name: str,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str = "",
    ) -> etree._Element | None:
        """Build an XML element based on its DTD declaration."""
        element_decl = self._find_element_by_name(element_name)
        if element_decl is None:
            # Unknown element, create with text content
            element = etree.Element(element_name)
            element.text = self._faker.word()
            return element

        current_path = f"{path}/{element_name}" if path else element_name
        element = etree.Element(element_name)

        # Check for override value for the element's text content
        if values and current_path in values:
            element.text = str(values[current_path])
            self._build_attributes(
                element, element_decl, values, optional_probability, current_path
            )
            return element

        # Build content based on content type
        content = element_decl.content
        if content is None:
            # EMPTY element
            pass
        else:
            self._build_content(
                element,
                content,
                values,
                optional_probability,
                max_occurs,
                current_path,
            )

        # Build attributes
        self._build_attributes(
            element, element_decl, values, optional_probability, current_path
        )

        return element

    def _build_content(
        self,
        parent: etree._Element,
        content: _DTDElementContent,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        """Build content for an element based on its DTD content model."""
        match content.type:
            case "pcdata":
                parent.text = self._generate_pcdata()

            case "element":
                # Single element reference
                child_name = content.name
                if child_name:
                    self._build_child_with_occur(
                        parent,
                        child_name,
                        content.occur,
                        values,
                        optional_probability,
                        max_occurs,
                        path,
                    )

            case "seq":
                # Sequence of elements
                self._build_sequence_content(
                    parent,
                    content,
                    values,
                    optional_probability,
                    max_occurs,
                    path,
                )

            case "or":
                # Choice between elements
                self._build_choice_content(
                    parent,
                    content,
                    values,
                    optional_probability,
                    max_occurs,
                    path,
                )

    def _build_sequence_content(
        self,
        parent: etree._Element,
        content: _DTDElementContent,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        """Build content for a sequence (a, b, c)."""
        # Handle the overall sequence occurrence
        occur = content.occur
        if occur == "mult":  # *
            count = self._random.randint(0, max_occurs)
        elif occur == "plus":  # +
            count = self._random.randint(1, max_occurs)
        elif occur == "opt":  # ?
            count = 1 if self._should_include_optional(optional_probability) else 0
        else:  # once
            count = 1

        for _ in range(count):
            # Process left and right parts of the sequence
            left = content.left
            right = content.right

            if left is not None:
                self._build_content_part(
                    parent, left, values, optional_probability, max_occurs, path
                )

            if right is not None:
                self._build_content_part(
                    parent, right, values, optional_probability, max_occurs, path
                )

    def _build_choice_content(
        self,
        parent: etree._Element,
        content: _DTDElementContent,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        """Build content for a choice (a | b | c)."""
        # Collect all choices
        choices = self._collect_choices(content)

        # Handle the overall choice occurrence
        occur = content.occur
        if occur == "mult":  # *
            count = self._random.randint(0, max_occurs)
        elif occur == "plus":  # +
            count = self._random.randint(1, max_occurs)
        elif occur == "opt":  # ?
            count = 1 if self._should_include_optional(optional_probability) else 0
        else:  # once
            count = 1

        for _ in range(count):
            if choices:
                chosen = self._random.choice(choices)
                self._build_content_part(
                    parent, chosen, values, optional_probability, max_occurs, path
                )

    def _collect_choices(
        self, content: _DTDElementContent
    ) -> list[_DTDElementContent]:
        """Recursively collect all choices from an 'or' content model."""
        choices: list[_DTDElementContent] = []

        if content.type == "or":
            if content.left is not None:
                if content.left.type == "or":
                    choices.extend(self._collect_choices(content.left))
                else:
                    choices.append(content.left)

            if content.right is not None:
                if content.right.type == "or":
                    choices.extend(self._collect_choices(content.right))
                else:
                    choices.append(content.right)
        else:
            choices.append(content)

        return choices

    def _build_content_part(
        self,
        parent: etree._Element,
        content: _DTDElementContent,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        """Build a single part of a content model."""
        match content.type:
            case "pcdata":
                if parent.text:
                    parent.text += " " + self._generate_pcdata()
                else:
                    parent.text = self._generate_pcdata()

            case "element":
                child_name = content.name
                if child_name:
                    self._build_child_with_occur(
                        parent,
                        child_name,
                        content.occur,
                        values,
                        optional_probability,
                        max_occurs,
                        path,
                    )

            case "seq":
                self._build_sequence_content(
                    parent, content, values, optional_probability, max_occurs, path
                )

            case "or":
                self._build_choice_content(
                    parent, content, values, optional_probability, max_occurs, path
                )

    def _build_child_with_occur(
        self,
        parent: etree._Element,
        child_name: str,
        occur: str,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        """Build child element(s) based on occurrence indicator."""
        match occur:
            case "mult":  # *
                count = self._random.randint(0, max_occurs)
            case "plus":  # +
                count = self._random.randint(1, max_occurs)
            case "opt":  # ?
                count = 1 if self._should_include_optional(optional_probability) else 0
            case _:  # once
                count = 1

        for _ in range(count):
            child = self._build_element(
                child_name, values, optional_probability, max_occurs, path
            )
            if child is not None:
                parent.append(child)

    def build(
        self,
        *,
        root_element: str | None = None,
        values: dict[str, Any] | None = None,
        optional_probability: float = 0.5,
        max_occurs: int = 3,
        seed: int | None = None,
    ) -> etree._Element:
        """Build a fake XML document based on the DTD.

        Args:
            root_element: The name of the root element to generate. If None and
                         only one element is defined, it will be used automatically.
            values: Dictionary of path -> value overrides. Paths use XPath-like
                   notation (e.g., "person/name", "person/@id").
            optional_probability: Probability (0-1) of including optional elements.
            max_occurs: Maximum number of repetitions for unbounded elements.
            seed: Random seed for reproducible generation.

        Returns:
            The generated XML element tree.

        Raises:
            ValueError: If no root element specified and multiple elements exist,
                       or if the specified root element is not found.
        """
        if seed is not None:
            self._random.seed(seed)
            Faker.seed(seed)

        self._load_dtd()

        # Find root element
        if root_element is None:
            root_elements = self._find_root_elements()
            if len(root_elements) == 0:
                raise ValueError("No elements found in DTD")
            if len(root_elements) > 1:
                raise ValueError(
                    f"Multiple elements found: {root_elements}. "
                    "Please specify root_element parameter."
                )
            root_name = root_elements[0]
        else:
            if self._find_element_by_name(root_element) is None:
                raise ValueError(f"Root element '{root_element}' not found in DTD")
            root_name = root_element

        # Build the XML tree
        xml_element = self._build_element(
            root_name, values, optional_probability, max_occurs
        )

        if xml_element is None:
            raise ValueError("Failed to build XML element")

        return xml_element
