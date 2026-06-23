# -*- coding: utf-8 -*-
from inspect import Parameter, Signature
from typing import Callable
from IPython.display import Markdown, display
from rich.console import Console
from rich.syntax import Syntax
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import Terminal256Formatter
from docstring_parser.common import DocstringParam
import docstring_parser
import functools
import inspect
import re
import textwrap
import warnings

# region: public
class MarkdownFormatting:
    """ Helper for formatting markdown text. """
    __slots__ = (
        # Original text to be formatted:
        "text",
        # Lines of the original text:
        "lines",
        # Normalized lines after processing:
        "normalized",
        # Current paragraph being built:
        "paragraph",
        # Whether we are currently inside a code fence:
        "in_fence",
        # Marker used for the current code fence (e.g. ``` or ~~~):
        "fence_marker",
        # Prefix used for list continuations (e.g. "    " for a nested list):
        "list_continuation_prefix",
        # Count of consecutive blank lines:
        "blank_count"
    )

    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.splitlines()

        self.normalized = []
        self.paragraph = []

        self.in_fence = False
        self.fence_marker = None
        self.list_continuation_prefix = None
        self.blank_count = 0

    @staticmethod
    def is_markdown_block_line(line: str) -> bool:
        stripped = line.lstrip()

        if not stripped:
            return True


        patterns = (
            r"#{1,6}\s",           # ATX headings: #, ##, ..., ######
            r">",                  # Blockquotes
            r"([-*_])\1{2,}\s*$",  # Thematic breaks: ---, ***, ___
            r"(```|~~~)",          # Fenced code block delimiters
            r"(:::)\s*",           # Quarto callout/admonition fences
            r"([-+*]|\d+\.)\s",    # Unordered and ordered list items
            r"\|",                 # Table rows using pipe syntax
            r"<[^>]+>",            # HTML block lines/tags
        )

        if any(re.match(pattern, stripped) for pattern in patterns):
            return True

        indent = len(line) - len(line.lstrip(" "))
        return indent >= 4

    @staticmethod
    def parse_list_item(line: str) -> tuple[str, str] | None:
        """ Determine if a line is a list item and return its elements. """
        if not (match := re.match(r"^(\s*)([-+*]|\d+\.)(\s+).*$", line)):
            return None

        leading, marker, spacing = match.groups()
        prefix = f"{leading}{' ' * (len(marker) + len(spacing))}"

        return leading, prefix

    def _flush_paragraph(self) -> None:
        """ Flush the current paragraph into the normalized list. """
        if self.paragraph:
            stripped = (p.strip() for p in self.paragraph)
            self.normalized.append(" ".join(stripped))
            self.paragraph.clear()

    def _is_aligned_with_list(self, line: str) -> bool:
        if self.list_continuation_prefix is None:
            return False

        return line.startswith(self.list_continuation_prefix)

    def _is_fence_line(self, line: str) -> bool:
        return re.match(r"(```|~~~)", line.lstrip()) is not None

    def _handle_fence_line(self, line: str) -> bool:
        if not self._is_fence_line(line):
            return False

        self._flush_paragraph()

        if not (matches := re.match(r"(```|~~~)", line.lstrip())):
            return False

        marker = matches.group(1)
        self.list_continuation_prefix = None
        self.blank_count = 0

        if self.in_fence and marker == self.fence_marker:
            self.in_fence = False
            self.fence_marker = None
        else:
            self.in_fence = True
            self.fence_marker = marker

        self.normalized.append(line)
        return True

    def _handle_in_fence_line(self, line: str) -> bool:
        if not self.in_fence:
            return False

        self.normalized.append(line)
        return True

    def _handle_blank_line(self) -> bool:
        self._flush_paragraph()
        self.blank_count += 1

        if self.blank_count >= 2:
            self.list_continuation_prefix = None

        if self.normalized and self.normalized[-1] != "":
            self.normalized.append("")

        return True

    def _handle_list_item_line(self, line: str) -> bool:
        if not (list_match := self.parse_list_item(line)):
            return False

        self._flush_paragraph()
        _, self.list_continuation_prefix = list_match
        self.normalized.append(line)
        return True

    def _handle_list_continuation(self, line: str) -> bool:
        if self.list_continuation_prefix is None:
            return False

        is_block = self.is_markdown_block_line(line)
        is_align = self._is_aligned_with_list(line)

        if is_block and not is_align:
            self.list_continuation_prefix = None
            return False

        self._flush_paragraph()

        if self.normalized:
            previous = self.normalized[-1].rstrip()
            continuation = line.strip()

            if continuation:
                self.normalized[-1] = f"{previous} {continuation}"
        else:
            new_line = f"{self.list_continuation_prefix}{line.strip()}"
            self.normalized.append(new_line)

        return True

    def _handle_markdown_block_line(self, line: str) -> bool:
        if not self.is_markdown_block_line(line):
            return False

        self._flush_paragraph()
        self.list_continuation_prefix = None
        self.normalized.append(line)
        return True

    def _handle_paragraph_line(self, line: str) -> None:
        self.list_continuation_prefix = None
        self.paragraph.append(line)

    def normalize(self) -> str:
        for line in self.lines:
            if self._handle_fence_line(line):
                continue

            if self._handle_in_fence_line(line):
                continue

            if not line.strip():
                self._handle_blank_line()
                continue

            self.blank_count = 0

            if self._handle_list_item_line(line):
                continue

            if self._handle_list_continuation(line):
                continue

            if self._handle_markdown_block_line(line):
                continue

            self._handle_paragraph_line(line)

        self._flush_paragraph()
        return "\n".join(self.normalized).strip()

    @classmethod
    def normalize_wrapping(cls, text: str) -> str:
        return cls(text).normalize()


class SignatureEntry:
    """ Builds the representation of a function signature.

    Parameters
    ----------
    fn : object
        The function to build the signature for.
    greedy : bool
        Whether to raise errors for missing docstrings or parameters.
    """
    def __init__(self, fn: type, *, greedy: bool = True) -> None:
        self.fn = fn
        self.doc = docstring_parser.parse(self.fn.__doc__ or "")
        self.sig = inspect.signature(fn)

        self.greedy = greedy
        self.lexer = PythonLexer()
        self.termf = Terminal256Formatter()

        self._vals = []
        self._docs = []

        self._sig_text = ""
        self._doc_text = ""

        self._seek_slashed = False
        self._seek_starred = False

        self._buffer = {}

        self._checks()
        self._scan()

    def __str__(self) -> str:
        return self._sig_text + "\n\n" + self._doc_text

    def _checks(self):
        n_doc = len(self.doc.params)
        n_sig = len(self.sig.parameters.items())

        if not self.doc:
            self._handle_greedy(
                f"Function '{self.fn.__name__}' has no docstring!")

        if self.doc and not self.doc.short_description:
            self._handle_greedy(
                f"Function '{self.fn.__name__}' has no summary!")

        # XXX: there is a special case where the signature contains only
        # starred parameters. The variadic parameters are expected to be
        # documented in the docstring (count 1) and at least one individual
        # keyword-only parameter is expected to be documented (count 2).
        # In this situation, no error is raised here but may be later when
        # scanning the signature.

        if n_sig > 0 and inspect.isfunction(self.fn):
            maybe_self = next(iter(self.sig.parameters.keys()))
            if maybe_self in ("self", "cls"):
                n_sig -= 1

        if n_doc < n_sig:
            self._handle_greedy(
                f"Function '{self.fn.__name__}' has {n_doc} "
                f"documented parameters, but {n_sig} parameters!")

    def _scan(self):
        # Build a buffer of the docstring parameters for retrieval
        # during signature scanning. Values are popped from the buffer.
        self._buffer = {p.arg_name: p for p in self.doc.params}

        # Iterate through the signature parameters and build the
        # signature text for each parameter not hidden in **kwargs.
        for p in self.sig.parameters.values():
            self._handle_entry(p)

        # Handle the remaining **kwargs doc here. This assumes that
        # the author maybe documented some of the variadic parameters
        # in the docstring (and maybe not all of them).
        for pdoc in self._buffer.copy().values():
            self._add_kward_doc(pdoc)

        # If there are any remaining parameters, they were not
        # documented (we should never end here as per above!)
        if self._buffer:
            names = list(self._buffer.keys())
            self._handle_greedy(
                f"Function '{self.fn.__name__}' has {len(names)} "
                f"undocumented parameters: {', '.join(names)}!")

        self._sig_text = self._handle_signature()
        self._doc_text = self._handle_docstring()

    def _handle_greedy(self, msg: str) -> None:
        if not self.greedy:
            warnings.warn(msg)
        else:
            raise ValueError(f"{msg} (greedy mode enabled)")

    def _handle_entry(self, p: Parameter) -> None:
        self._handle_positional_only(p)
        self._handle_keyword_only(p)
        self._vals.append(f"    {self._represent(p)}")

        if p.kind != Parameter.VAR_KEYWORD:
            self._add_param_doc(p)

    def _handle_positional_only(self, p: Parameter) -> None:
        if p.kind == Parameter.POSITIONAL_ONLY:
            self._seek_slashed = True
        elif self._seek_slashed and p.kind != Parameter.POSITIONAL_ONLY:
            self._vals.append(f"    /")
            self._seek_slashed = False

    def _handle_keyword_only(self, p: Parameter) -> None:
        if not self._seek_starred and p.kind == Parameter.KEYWORD_ONLY:
            self._vals.append(f"    *")
            self._seek_starred = True

    def _handle_signature(self) -> str:
        name = self.fn.__name__
        returns = self.sig.return_annotation

        if not self._vals:
            signature = f"{name}()"
        elif len(self._vals) == 1:
            signature = f"{name}({self._vals[0].strip()}):"
        else:
            signature = f"{name}(\n{',\n'.join(self._vals)}\n    )"

        if returns is Signature.empty:
            signature = f"{signature}:"
        elif isinstance(returns, type):
            signature = f"{signature} -> {returns.__name__}:"
        else:
            signature = f"{signature} -> {str(returns)}:"

        return signature

    def _handle_docstring(self) -> str:
        width = 66
        spaces = " " * 4
        docs = "\n(missing summary)"

        if self.doc and self.doc.short_description:
            docs = f"\n{self.doc.short_description}"

        # TODO handle long description!

        if self._docs:
            docs += "\n\n\nParameters\n----------"

            for entry in self._docs:
                head = entry["annotated"]
                body = entry["description"]

                body = textwrap.fill(
                    text             = body,
                    width            = width,
                    initial_indent   = spaces,
                    subsequent_indent= spaces
                )
                docs += f"\n{head}\n{body}"

        return docs

    def _add_param_doc(self, p: Parameter) -> None:
        annotated = self._represent(p)
        entry = {"annotated": annotated, "description": ""}

        if p.name in ("self", "cls"):
            return

        if p.name not in self._buffer:
            self._handle_greedy(
                f"Parameter '{p.name}' not found in docstring for "
                f"function '{self.fn.__name__}'!")

        try:
            if (doc := self._buffer.pop(p.name)).description:
                descr = " ".join(doc.description.split("\n"))
                entry["description"] = descr
        except KeyError:
            entry["description"] = "(missing description)"

        self._docs.append(entry)

    def _add_kward_doc(self, pdoc: DocstringParam) -> None:
        annotation = pdoc.type_name
        default = None

        if annotation and "=" in annotation:
            try:
                annotation, default = annotation.split("=")
                default = default.strip()
            except ValueError:
                pass

        # TODO: notice that no matter what the type of the annotation,
        # it is always treated as a string. Find a way around sometime...
        p = Parameter(pdoc.arg_name, Parameter.KEYWORD_ONLY,
                      annotation=annotation, default=default)

        self._add_param_doc(p)

    def _highlight(self, text: str) -> str:
        return highlight(text, self.lexer, self.termf)

    def _represent(self, p: Parameter) -> str:
        annotated = self.get_annotated(p)

        if not (default := self.get_default(p)):
            entry = annotated
        else:
            entry = f"{annotated} = {default}"

        return entry.strip()

    @staticmethod
    def code_fences(code: str) -> str:
        """ Wraps a piece of code in markdown code fences.

        Parameters
        ----------
        code : str
            The code to wrap in markdown code fences.
        """
        return f"\n\n```python\n{code.rstrip()}\n```\n\n"

    @staticmethod
    def get_annotated(p: Parameter) -> str:
        """ Returns the annotated version of the parameter.

        Parameters
        ----------
        p : Parameter
            The parameter to annotate.
        """
        annotated = (f"{SignatureEntry.get_name(p)} : "
                     f"{SignatureEntry.get_annotation(p)}")
        return annotated

    @staticmethod
    def get_name(p: Parameter) -> str:
        """ Returns the name of the parameter.

        Notice that this handles the special cases of stars in variadic
        parameters (e.g. *args, **kwargs), which are not directly
        represented in the parameter name.

        Parameters
        ----------
        p : Parameter
            The parameter to get the name of.
        """
        if p.kind == Parameter.VAR_POSITIONAL:
            return f"*{p.name}"

        if p.kind == Parameter.VAR_KEYWORD:
            return f"**{p.name}"

        return p.name

    @staticmethod
    def get_annotation(p: Parameter) -> str:
        """ Returns the annotation of the parameter.

        Parameters
        ----------
        p : Parameter
            The parameter to retrieve the annotation from.
        """
        if p.annotation is Parameter.empty:
            return "Any"
        elif isinstance(p.annotation, type):
            return p.annotation.__name__
        else:
            return str(p.annotation)

    @staticmethod
    def get_default(p: Parameter) -> str:
        """ Returns the default value of the parameter.

        Parameters
        ----------
        p : Parameter
            The parameter to retrieve the default value from.
        """
        if p.default is Parameter.empty:
            return ""
        elif isinstance(p.default, str):
            return f"'{p.default}'"
        else:
            return f"{p.default}"

    def _fmt_description(self) -> str:
        text = ""

        if short := self.doc.short_description:
            text += f"{short}\n\n"
        else:
            text += "(missing summary)\n\n"

        if long := self.doc.long_description:
            long = MarkdownFormatting.normalize_wrapping(long)
            text += f"{long}\n\n"

        return text

    def _fmt_parameter(self, entry: dict) -> str:
        spaces = "&nbsp;" * 4

        head = entry["annotated"]
        body = entry["description"]

        # text = self.code_fences(head)
        # text += f"<p>{spaces}{body}</p>\n\n"

        text = "\n".join([
            r'<div class="row" style="font-size: 0.8em;">',
            self.code_fences(head),
            r'</div>',
            r'<div class="row" style="margin-top: -2em; font-size: 0.8em;">',
            f'  <div class="col-2">{spaces}</div>',
            f'  <div class="col-10">{body}</div>',
            r'</div>',
        ])

        return text

    def _fmt_parameters_section(self) -> str:
        text = "\n***\n\n**Parameters**\n"

        for entry in self._docs:
            text += self._fmt_parameter(entry)

        return text

    def documentation(self, **kwargs) -> None:
        """ Generates the markdown documentation for the function.

        Parameters
        ----------
        title : str
            The title to use for the section header and callout. By
            default, the function name is used.
        """
        title = kwargs.get("title", self.fn.__name__)

        # <div class="callout callout-note">
        #   <div class="callout-header">
        #     <div class="callout-title">My Title</div>
        #   </div>
        #   <div class="callout-body">
        #     <p>Content here.</p>
        #   </div>
        # </div>

        text = ""
        text += f"""::: {{.callout-note title="{title}"}}"""
        text += self.code_fences(self._sig_text)

        if self.doc:
            text += self._fmt_description()

        if self._docs:
            text += self._fmt_parameters_section()

        text += f":::\n\n"

        # print(text)
        display(Markdown(text))


class DocumentedClass:
    """ Helper for documenting all members of a class. """
    def __init__(self, cls: type) -> None:
        self.cls = cls

    @staticmethod
    def _doc_it(fn, **kwargs):
        entry = SignatureEntry(fn, **kwargs)
        entry.documentation(**kwargs)

    @staticmethod
    def _members_from_dict(
            objcls: type,
            predicate: Callable[[str, object], None],
            **kwargs
        ) -> None:
        public_only = kwargs.get("public_only", True)

        for name, func in objcls.__dict__.items():
            if public_only and DocumentedClass._is_private(name):
                continue

            predicate(name, func, **kwargs)

    @staticmethod
    def _is_private(name: str) -> bool:
        private = name.startswith("_")
        dunder = DocumentedClass._is_dunder(name)
        return private and not dunder

    @staticmethod
    def _is_dunder(name: str) -> bool:
        return name.startswith("__") and name.endswith("__")

    def _dunders(self, name, func, **kwargs) -> None:
        # XXX improve these, maybe test for modules, etc...
        is_callable = callable(func)
        is_dunder = DocumentedClass._is_dunder(name)

        # XXX notice that we skip undocumented dunders, even in
        # greedy mode. This is because some dunders are not meant
        # to be documented (e.g. __dict__, __weakref__, etc.)
        if is_dunder and is_callable and func.__doc__:
            DocumentedClass._doc_it(func, **kwargs)

    def _members(self, name, func, **kwargs) -> None:
        disallow = (staticmethod, classmethod, property)

        is_callable = callable(func)
        is_allowed  = not isinstance(func, disallow)
        is_dunder = DocumentedClass._is_dunder(name)

        if is_allowed and is_callable and not is_dunder:
            DocumentedClass._doc_it(func, **kwargs)

    def _properties(self, name, func, **kwargs) -> None:
        if isinstance(func, property):
            DocumentedClass._doc_it(func.fget, **kwargs)

    def _classmethods(self, name, func, **kwargs) -> None:
        if isinstance(func, classmethod):
            DocumentedClass._doc_it(func.__func__, **kwargs)

    def _staticmethods(self, name, func, **kwargs) -> None:
        if isinstance(func, staticmethod):
            DocumentedClass._doc_it(func.__func__, **kwargs)

    def constructor(self, **kwargs) -> None:
        entry = SignatureEntry(self.cls)
        entry.documentation(**kwargs)

    def members(self, **kwargs) -> None:
        self._members_from_dict(self.cls, self._members, **kwargs)

    def properties(self, **kwargs) -> None:
        self._members_from_dict(self.cls, self._properties, **kwargs)

    def classmethods(self, **kwargs) -> None:
        self._members_from_dict(self.cls, self._classmethods, **kwargs)

    def staticmethods(self, **kwargs) -> None:
        self._members_from_dict(self.cls, self._staticmethods, **kwargs)

    def dunders(self, **kwargs) -> None:
        self._members_from_dict(self.cls, self._dunders, **kwargs)
# endregion: public

# region: internals


def with_attrs(**attrs):
    def wrap(fn):
        for k, v in attrs.items():
            setattr(fn, k, v)

        @functools.wraps(fn)
        def inner(*args, **kwargs):
            return fn(*args, **kwargs)

        return inner
    return wrap


@with_attrs(console=True)
def print_signature(
        signature: str,
        width: int | None = None,
        parse_syntax: bool = False
    ) -> None:
    """ Print a function signature with syntax highlighting.

    This function is required as the default printing will strip colors
    and without configuration, rich.print will wrap long lines (from the
    standpoint of ANSI color codes) which can lead to broken formatting.
    If soft_wrap fails for some reason, try setting width to a large
    number (e.g. 200, accounting for ANSI color codes).
    """
    if not getattr(print_signature, "console", True):
        print(signature)
        return

    console = Console(width=width, soft_wrap=True)

    if parse_syntax:
        syntax = Syntax(signature, "python")
        console.print(syntax)
    else:
        console.print(signature)


def test_for_func(f, *, greedy=False):
    entry = SignatureEntry(f, greedy=greedy)
    entry.documentation()

    try:
        SignatureEntry(f, greedy=True)
    except ValueError:
        pass
# endregion: internals