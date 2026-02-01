from io import BytesIO
from pathlib import Path
from random import Random
from typing import Any, Self, cast

from faker import Faker
from lxml import etree

XSD_NS = "http://www.w3.org/2001/XMLSchema"
XSD = "{%s}" % XSD_NS
NSMAP: dict[str, str] = {"xs": XSD_NS}


class XMLFactory:
    def __init__(
        self,
        schema: BytesIO | str | Path,
        *,
        locale: str | list[str] | None = None,
    ) -> None:
        self._schema_source = schema
        self._schema: etree.XMLSchema | None = None
        self._schema_tree: etree._ElementTree | None = None
        self._faker = Faker(locale)
        self._random = Random()

    def _load_schema(self) -> etree.XMLSchema:
        if self._schema is not None:
            return self._schema

        match self._schema_source:
            case BytesIO() as bio:
                bio.seek(0)
                self._schema_tree = etree.parse(bio)
            case Path() as path:
                self._schema_tree = etree.parse(path)
            case str() as content:
                root = etree.fromstring(content.encode())
                self._schema_tree = root.getroottree()

        assert self._schema_tree is not None
        self._schema = etree.XMLSchema(self._schema_tree)
        return self._schema

    def _get_schema_tree(self) -> etree._ElementTree:
        if self._schema_tree is None:
            self._load_schema()
        assert self._schema_tree is not None
        return self._schema_tree

    def with_locale(self, locale: str | list[str]) -> Self:
        self._faker = Faker(locale)
        return self

    def _find_root_elements(self) -> list[etree._Element]:
        tree = self._get_schema_tree()
        result = tree.xpath("/xs:schema/xs:element", namespaces=NSMAP)
        return cast(list[etree._Element], result)

    def _find_element_by_name(self, name: str) -> etree._Element | None:
        tree = self._get_schema_tree()
        elements = cast(
            list[etree._Element],
            tree.xpath(f"/xs:schema/xs:element[@name='{name}']", namespaces=NSMAP),
        )
        return elements[0] if elements else None

    def _find_type_by_name(self, type_name: str) -> etree._Element | None:
        tree = self._get_schema_tree()
        # Handle namespace prefix
        if ":" in type_name:
            prefix, local_name = type_name.split(":", 1)
            if prefix == "xs":
                return None  # Built-in type
            type_name = local_name

        # Search for complexType or simpleType
        for tag in ["complexType", "simpleType"]:
            types = cast(
                list[etree._Element],
                tree.xpath(
                    f"/xs:schema/xs:{tag}[@name='{type_name}']", namespaces=NSMAP
                ),
            )
            if types:
                return types[0]
        return None

    def _is_builtin_type(self, type_name: str | None) -> bool:
        if type_name is None:
            return False
        if ":" in type_name:
            prefix, _ = type_name.split(":", 1)
            return prefix == "xs"
        return False

    def _generate_builtin_value(self, type_name: str) -> str:
        if ":" in type_name:
            _, local_name = type_name.split(":", 1)
        else:
            local_name = type_name

        match local_name:
            case "string":
                return self._faker.word()
            case "integer" | "int" | "long" | "short":
                return str(self._faker.random_int(min=-1000, max=1000))
            case "positiveInteger":
                return str(self._faker.random_int(min=1, max=1000))
            case "nonNegativeInteger":
                return str(self._faker.random_int(min=0, max=1000))
            case "negativeInteger":
                return str(self._faker.random_int(min=-1000, max=-1))
            case "decimal" | "float" | "double":
                return str(
                    round(self._faker.pyfloat(min_value=-1000, max_value=1000), 2)
                )
            case "boolean":
                return self._random.choice(["true", "false"])
            case "date":
                return self._faker.date()
            case "dateTime":
                return self._faker.iso8601()
            case "time":
                return self._faker.time()
            case "duration":
                return f"P{self._faker.random_int(min=1, max=30)}D"
            case "gYear":
                return str(self._faker.year())
            case "gMonth":
                return f"--{self._faker.random_int(min=1, max=12):02d}"
            case "gDay":
                return f"---{self._faker.random_int(min=1, max=28):02d}"
            case "gYearMonth":
                return (
                    f"{self._faker.year()}-{self._faker.random_int(min=1, max=12):02d}"
                )
            case "gMonthDay":
                return f"--{self._faker.random_int(min=1, max=12):02d}-{self._faker.random_int(min=1, max=28):02d}"
            case "hexBinary":
                return self._faker.hexify(text="^^^^^^^^^^^^")
            case "base64Binary":
                return self._faker.binary(length=12).hex()
            case "anyURI":
                return self._faker.url()
            case "QName" | "NOTATION":
                return self._faker.word()
            case "normalizedString":
                return self._faker.word()
            case "token" | "language" | "Name" | "NCName" | "ID" | "IDREF" | "ENTITY":
                return self._faker.word()
            case "NMTOKEN":
                return self._faker.word()
            case "byte":
                return str(self._faker.random_int(min=-128, max=127))
            case "unsignedByte":
                return str(self._faker.random_int(min=0, max=255))
            case "unsignedShort":
                return str(self._faker.random_int(min=0, max=65535))
            case "unsignedInt":
                return str(self._faker.random_int(min=0, max=1000000))
            case "unsignedLong":
                return str(self._faker.random_int(min=0, max=1000000))
            case _:
                return self._faker.word()

    def _get_element_type(self, element: etree._Element) -> str | None:
        return element.get("type")

    def _should_include_optional(self, optional_probability: float) -> bool:
        return self._random.random() < optional_probability

    def _get_occurs(
        self, element: etree._Element, max_occurs_limit: int
    ) -> tuple[int, int]:
        min_occurs = int(element.get("minOccurs", "1"))
        max_occurs_str = element.get("maxOccurs", "1")
        if max_occurs_str == "unbounded":
            max_occurs = max_occurs_limit
        else:
            max_occurs = min(int(max_occurs_str), max_occurs_limit)
        return min_occurs, max_occurs

    def _resolve_element_ref(self, element: etree._Element) -> etree._Element | None:
        ref = element.get("ref")
        if ref is None:
            return element
        if ":" in ref:
            _, ref = ref.split(":", 1)
        return self._find_element_by_name(ref)

    def _build_element(
        self,
        element_def: etree._Element,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str = "",
    ) -> etree._Element | None:
        # Handle element references
        resolved_def = self._resolve_element_ref(element_def)
        if resolved_def is None:
            return None
        element_def = resolved_def

        element_name = element_def.get("name")
        if element_name is None:
            return None

        current_path = f"{path}/{element_name}" if path else element_name
        target_ns = self._get_schema_tree().getroot().get("targetNamespace")

        if target_ns:
            element = etree.Element(f"{{{target_ns}}}{element_name}")
        else:
            element = etree.Element(element_name)

        # Check for override value
        if values and current_path in values:
            element.text = str(values[current_path])
            return element

        # Get element type
        type_name = self._get_element_type(element_def)

        # Handle inline type definition
        inline_complex = element_def.find(f"{XSD}complexType")
        inline_simple = element_def.find(f"{XSD}simpleType")

        if inline_complex is not None:
            self._build_complex_content(
                element,
                inline_complex,
                values,
                optional_probability,
                max_occurs,
                current_path,
            )
        elif inline_simple is not None:
            element.text = self._build_simple_type_value(inline_simple)
        elif type_name:
            if self._is_builtin_type(type_name):
                element.text = self._generate_builtin_value(type_name)
            else:
                type_def = self._find_type_by_name(type_name)
                if type_def is not None:
                    if type_def.tag == f"{XSD}complexType":
                        self._build_complex_content(
                            element,
                            type_def,
                            values,
                            optional_probability,
                            max_occurs,
                            current_path,
                        )
                    else:
                        element.text = self._build_simple_type_value(type_def)
                else:
                    element.text = self._faker.word()
        else:
            # No type specified, use string
            element.text = self._faker.word()

        # Handle attributes
        self._build_attributes(
            element, element_def, values, optional_probability, current_path
        )

        return element

    def _build_attributes(
        self,
        element: etree._Element,
        element_def: etree._Element,
        values: dict[str, Any] | None,
        optional_probability: float,
        path: str,
    ) -> None:
        # Get type definition for attributes
        type_name = self._get_element_type(element_def)
        type_def = None
        if type_name and not self._is_builtin_type(type_name):
            type_def = self._find_type_by_name(type_name)

        # Check inline complexType
        inline_complex = element_def.find(f"{XSD}complexType")
        if inline_complex is not None:
            type_def = inline_complex

        if type_def is None:
            return

        # Find attributes in the type definition
        for attr in type_def.iter(f"{XSD}attribute"):
            attr_name = attr.get("name")
            if attr_name is None:
                # Handle attribute reference
                ref = attr.get("ref")
                if ref:
                    if ":" in ref:
                        _, attr_name = ref.split(":", 1)
                    else:
                        attr_name = ref

            if attr_name is None:
                continue

            attr_path = f"{path}/@{attr_name}"
            use = attr.get("use", "optional")

            # Check for override
            if values and attr_path in values:
                element.set(attr_name, str(values[attr_path]))
                continue

            if use == "required" or self._should_include_optional(optional_probability):
                attr_type = attr.get("type", "xs:string")
                element.set(attr_name, self._generate_builtin_value(attr_type))

    def _build_complex_content(
        self,
        element: etree._Element,
        type_def: etree._Element,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        # Handle sequence
        sequence = type_def.find(f"{XSD}sequence")
        if sequence is not None:
            self._build_sequence(
                element, sequence, values, optional_probability, max_occurs, path
            )
            return

        # Handle choice
        choice = type_def.find(f"{XSD}choice")
        if choice is not None:
            self._build_choice(
                element, choice, values, optional_probability, max_occurs, path
            )
            return

        # Handle all
        all_group = type_def.find(f"{XSD}all")
        if all_group is not None:
            self._build_all(
                element, all_group, values, optional_probability, max_occurs, path
            )
            return

        # Handle simpleContent
        simple_content = type_def.find(f"{XSD}simpleContent")
        if simple_content is not None:
            extension = simple_content.find(f"{XSD}extension")
            if extension is not None:
                base = extension.get("base")
                if base:
                    element.text = self._generate_builtin_value(base)
            return

        # Handle complexContent
        complex_content = type_def.find(f"{XSD}complexContent")
        if complex_content is not None:
            extension = complex_content.find(f"{XSD}extension")
            if extension is not None:
                base = extension.get("base")
                if base:
                    base_type = self._find_type_by_name(base)
                    if base_type is not None:
                        self._build_complex_content(
                            element,
                            base_type,
                            values,
                            optional_probability,
                            max_occurs,
                            path,
                        )
                # Also process the extension's own content
                self._build_complex_content(
                    element, extension, values, optional_probability, max_occurs, path
                )

    def _build_sequence(
        self,
        parent: etree._Element,
        sequence: etree._Element,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        for child in sequence:
            if child.tag == f"{XSD}element":
                min_occ, max_occ = self._get_occurs(child, max_occurs)

                if min_occ == 0 and not self._should_include_optional(
                    optional_probability
                ):
                    continue

                count = self._random.randint(max(1, min_occ), max_occ)
                for _ in range(count):
                    child_element = self._build_element(
                        child, values, optional_probability, max_occurs, path
                    )
                    if child_element is not None:
                        parent.append(child_element)

            elif child.tag == f"{XSD}sequence":
                self._build_sequence(
                    parent, child, values, optional_probability, max_occurs, path
                )

            elif child.tag == f"{XSD}choice":
                self._build_choice(
                    parent, child, values, optional_probability, max_occurs, path
                )

            elif child.tag == f"{XSD}any":
                # Generate a generic element for xs:any
                any_element = etree.Element("anyElement")
                any_element.text = self._faker.word()
                parent.append(any_element)

    def _build_choice(
        self,
        parent: etree._Element,
        choice: etree._Element,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        children = [
            c
            for c in choice
            if c.tag in (f"{XSD}element", f"{XSD}sequence", f"{XSD}choice")
        ]
        if not children:
            return

        chosen = self._random.choice(children)

        if chosen.tag == f"{XSD}element":
            child_element = self._build_element(
                chosen, values, optional_probability, max_occurs, path
            )
            if child_element is not None:
                parent.append(child_element)
        elif chosen.tag == f"{XSD}sequence":
            self._build_sequence(
                parent, chosen, values, optional_probability, max_occurs, path
            )
        elif chosen.tag == f"{XSD}choice":
            self._build_choice(
                parent, chosen, values, optional_probability, max_occurs, path
            )

    def _build_all(
        self,
        parent: etree._Element,
        all_group: etree._Element,
        values: dict[str, Any] | None,
        optional_probability: float,
        max_occurs: int,
        path: str,
    ) -> None:
        elements = list(all_group.findall(f"{XSD}element"))
        self._random.shuffle(elements)

        for child in elements:
            min_occ, _ = self._get_occurs(child, 1)  # maxOccurs is always 1 in xs:all

            if min_occ == 0 and not self._should_include_optional(optional_probability):
                continue

            child_element = self._build_element(
                child, values, optional_probability, max_occurs, path
            )
            if child_element is not None:
                parent.append(child_element)

    def _build_simple_type_value(self, type_def: etree._Element) -> str:
        # Handle restriction
        restriction = type_def.find(f"{XSD}restriction")
        if restriction is not None:
            base = restriction.get("base", "xs:string")

            # Check for enumeration
            enumerations = restriction.findall(f"{XSD}enumeration")
            if enumerations:
                values = [e.get("value") for e in enumerations if e.get("value")]
                if values:
                    return self._random.choice(values)

            # Check for pattern
            pattern = restriction.find(f"{XSD}pattern")
            if pattern is not None:
                # For patterns, just return a basic value of the base type
                return self._generate_builtin_value(base)

            # Check for length constraints
            min_length = restriction.find(f"{XSD}minLength")
            max_length = restriction.find(f"{XSD}maxLength")
            length = restriction.find(f"{XSD}length")

            if length is not None:
                exact = int(length.get("value", "10"))
                return self._faker.pystr(min_chars=exact, max_chars=exact)
            elif min_length is not None or max_length is not None:
                min_len = (
                    int(min_length.get("value", "1")) if min_length is not None else 1
                )
                max_len = (
                    int(max_length.get("value", "20")) if max_length is not None else 20
                )
                return self._faker.pystr(min_chars=min_len, max_chars=max_len)

            # Check for numeric constraints
            min_inclusive = restriction.find(f"{XSD}minInclusive")
            max_inclusive = restriction.find(f"{XSD}maxInclusive")
            min_exclusive = restriction.find(f"{XSD}minExclusive")
            max_exclusive = restriction.find(f"{XSD}maxExclusive")

            has_constraints = any(
                el is not None
                for el in [min_inclusive, max_inclusive, min_exclusive, max_exclusive]
            )

            if has_constraints:
                min_val = -1000
                max_val = 1000

                if min_inclusive is not None:
                    min_val = int(min_inclusive.get("value", "-1000"))
                if max_inclusive is not None:
                    max_val = int(max_inclusive.get("value", "1000"))
                if min_exclusive is not None:
                    min_val = int(min_exclusive.get("value", "-1000")) + 1
                if max_exclusive is not None:
                    max_val = int(max_exclusive.get("value", "1000")) - 1

                return str(self._random.randint(min_val, max_val))

            return self._generate_builtin_value(base)

        # Handle union
        union = type_def.find(f"{XSD}union")
        if union is not None:
            member_types = union.get("memberTypes", "").split()
            if member_types:
                chosen_type = self._random.choice(member_types)
                return self._generate_builtin_value(chosen_type)

        # Handle list
        list_type = type_def.find(f"{XSD}list")
        if list_type is not None:
            item_type = list_type.get("itemType", "xs:string")
            count = self._random.randint(1, 5)
            items = [self._generate_builtin_value(item_type) for _ in range(count)]
            return " ".join(items)

        return self._faker.word()

    def build(
        self,
        *,
        root_element: str | None = None,
        values: dict[str, Any] | None = None,
        optional_probability: float = 0.5,
        max_occurs: int = 3,
        seed: int | None = None,
    ) -> etree._Element:
        if seed is not None:
            self._random.seed(seed)
            Faker.seed(seed)

        self._load_schema()

        # Find root element
        if root_element is None:
            root_elements = self._find_root_elements()
            if len(root_elements) == 0:
                raise ValueError("No root elements found in schema")
            if len(root_elements) > 1:
                names = [e.get("name") for e in root_elements]
                raise ValueError(
                    f"Multiple root elements found: {names}. "
                    "Please specify root_element parameter."
                )
            root_def = root_elements[0]
        else:
            root_def = self._find_element_by_name(root_element)
            if root_def is None:
                raise ValueError(f"Root element '{root_element}' not found in schema")

        # Build the XML tree
        xml_element = self._build_element(
            root_def, values, optional_probability, max_occurs
        )

        if xml_element is None:
            raise ValueError("Failed to build XML element")

        return xml_element
