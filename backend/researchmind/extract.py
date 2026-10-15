"""Knowledge extraction: methods, datasets, claims, findings and limitations.

Two extractors share one output shape:
  * HeuristicExtractor - rule/lexicon based, offline, deterministic.
  * ClaudeExtractor    - Claude with structured outputs; every item must cite a chunk id
                         and a verbatim quote that is verified against the chunk text.
Every extracted item keeps its evidence (chunk id + quote), so the graph can always
point back to the page it came from.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field

from .ingest import Chunk, ParsedPaper, _split_sentences

log = logging.getLogger(__name__)


@dataclass
class Item:
    text: str           # entity name (method/dataset) or statement text
    chunk_id: str       # evidence chunk
    quote: str          # verbatim supporting sentence
    kind: str = ""      # e.g. "limitation" | "future_work"


@dataclass
class Extraction:
    methods: list[Item] = field(default_factory=list)
    datasets: list[Item] = field(default_factory=list)
    claims: list[Item] = field(default_factory=list)
    findings: list[Item] = field(default_factory=list)
    limitations: list[Item] = field(default_factory=list)
    extractor: str = "heuristic"

    def to_dict(self) -> dict:
        return asdict(self)

    def counts(self) -> dict[str, int]:
        return {k: len(getattr(self, k)) for k in ("methods", "datasets", "claims", "findings", "limitations")}


# --------------------------------------------------------------------------- helpers

def slug(name: str) -> str:
    """Canonical id for shared entities so the same method links papers together."""
    s = name.lower().strip()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-(dataset|benchmark|corpus|model|network|networks)$", "", s)
    return ALIASES.get(s, s)


ALIASES = {
    "gat": "graph-attention-network", "graph-attention": "graph-attention-network",
    "gnn": "graph-neural-network", "graph-neural": "graph-neural-network",
    "cnn": "convolutional-neural-network", "convolutional-neural": "convolutional-neural-network",
    "rnn": "recurrent-neural-network", "lstm": "long-short-term-memory",
    "plm": "protein-language", "protein-language": "protein-language",
    "rag": "retrieval-augmented-generation", "mlp": "multilayer-perceptron",
    "transformers": "transformer", "bert-base": "bert",
}

METHOD_LEXICON = [
    "Graph Attention Network", "Graph Neural Network", "Convolutional Neural Network",
    "Recurrent Neural Network", "Multilayer Perceptron", "Transformer", "Self-Attention",
    "Protein Language Model", "Language Model", "Large Language Model", "Contrastive Learning",
    "Reinforcement Learning", "Transfer Learning", "Fine-Tuning", "Knowledge Distillation",
    "Variational Autoencoder", "Autoencoder", "Generative Adversarial Network", "Diffusion Model",
    "Retrieval-Augmented Generation", "Random Forest", "Support Vector Machine", "Logistic Regression",
    "Gradient Boosting", "XGBoost", "K-Means", "Bayesian Optimization", "Message Passing",
    "Equivariant Graph Neural Network", "Attention Mechanism", "LSTM", "BERT", "GPT", "ResNet", "U-Net",
    "ESM-2", "AlphaFold", "DeepDTA", "Word2Vec", "Node2Vec", "PCA",
]
ACRONYMS = {"GAT": "Graph Attention Network", "GNN": "Graph Neural Network", "CNN": "Convolutional Neural Network",
            "LSTM": "LSTM", "MLP": "Multilayer Perceptron", "RAG": "Retrieval-Augmented Generation"}

DATASET_LEXICON = [
    "ImageNet", "CIFAR-10", "CIFAR-100", "MNIST", "COCO", "SQuAD", "GLUE", "SuperGLUE", "WMT 2014",
    "PubMed", "MIMIC-III", "MIMIC-IV", "DAVIS", "KIBA", "BindingDB", "PDBbind", "ChEMBL", "ZINC",
    "QM9", "MoleculeNet", "Tox21", "UniProt", "OGB", "Cora", "Citeseer", "LibriSpeech", "Wikipedia",
]
DATASET_PATTERN = re.compile(r"\b(?:the\s+)?([A-Z][A-Za-z0-9\-]{1,30}(?:\s[A-Z0-9][A-Za-z0-9\-]{0,20})?)\s+(?:dataset|benchmark|corpus)\b")

CLAIM_CUES = re.compile(
    r"\b(we (propose|introduce|present|show|demonstrate|argue|find)|our (approach|method|model|results)|"
    r"this (paper|work)|outperform|state-of-the-art|is necessary|improves?|do(es)? not generalize|generalizes?)\b", re.I)
FINDING_CUES = re.compile(
    r"(\d+(\.\d+)?\s?%|\b(AUC|RMSE|F1|accuracy|BLEU|ROUGE|precision|recall|correlation)\b|"
    r"\b(results (show|indicate|suggest)|we (find|observe)|achieves?|reduces?|reaches?)\b)", re.I)
LIMIT_CUES = re.compile(
    r"\b(limitation|limited to|is limited|did not|does not|do not|cannot|fails? to|unavailable|"
    r"remains? (unclear|untested|open)|untested|high computational cost|requires?|ignores?|drawback|"
    r"not (evaluated|tested|considered))\b", re.I)
NEGATED_USE = re.compile(r"\b(did not|do not|does not|not (evaluated|tested)|untested|remains? untested|future work|should evaluate)\b", re.I)
FUTURE_CUES = re.compile(r"\b(future work|in the future|further (work|research)|should (evaluate|investigate|explore))\b", re.I)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def quote_in_chunk(quote: str, chunk_text: str) -> bool:
    q, t = _norm_ws(quote).lower(), _norm_ws(chunk_text).lower()
    if q in t:
        return True
    # tolerate small punctuation differences from the LLM
    strip = lambda x: re.sub(r"[^a-z0-9 ]", "", x)
    return len(q) > 15 and strip(q) in strip(t)


# --------------------------------------------------------------------------- heuristic

class HeuristicExtractor:
    name = "heuristic"
    MAX_STATEMENTS = 10

    def extract(self, paper: ParsedPaper) -> Extraction:
        out = Extraction(extractor=self.name)
        seen_methods: dict[str, Item] = {}
        seen_datasets: dict[str, Item] = {}

        for chunk in paper.chunks:
            section = chunk.section.lower()
            for sentence in _split_sentences(chunk.text):
                low = sentence.lower()

                # Entities named only in "did not evaluate X" / future-work sentences are not *used*.
                negated = bool(NEGATED_USE.search(sentence)) or "limitation" in section or "future" in section
                for term in ([] if negated else METHOD_LEXICON):
                    if re.search(rf"\b{re.escape(term.lower())}s?\b", low):
                        self._add_entity(seen_methods, term, chunk, sentence)
                for acr, full in ([] if negated else ACRONYMS.items()):
                    if re.search(rf"\b{acr}s?\b", sentence):
                        self._add_entity(seen_methods, full, chunk, sentence)
                for name in ([] if negated else DATASET_LEXICON):
                    if re.search(rf"\b{re.escape(name)}\b", sentence):
                        self._add_entity(seen_datasets, name, chunk, sentence)
                for m in ([] if negated else DATASET_PATTERN.finditer(sentence)):
                    cand = m.group(1).strip()
                    if cand.lower() not in {"the", "this", "our", "a", "each", "test", "training"}:
                        self._add_entity(seen_datasets, cand, chunk, sentence)

                if section == "front matter":
                    continue  # licences, affiliations, headers: entities above are fine, statements are not
                is_limit_section = "limitation" in section or "future" in section
                if FUTURE_CUES.search(sentence):
                    out.limitations.append(Item(sentence, chunk.id, sentence, "future_work"))
                elif (is_limit_section and len(sentence) > 30) or (LIMIT_CUES.search(sentence) and section in ("discussion", "conclusion")):
                    out.limitations.append(Item(sentence, chunk.id, sentence, "limitation"))
                elif FINDING_CUES.search(sentence) and section not in ("introduction", "related work", "front matter"):
                    out.findings.append(Item(sentence, chunk.id, sentence))
                elif CLAIM_CUES.search(sentence):
                    out.claims.append(Item(sentence, chunk.id, sentence))

        out.methods = self._dedupe_methods(list(seen_methods.values()))
        out.datasets = list(seen_datasets.values())
        out.claims = out.claims[: self.MAX_STATEMENTS]
        out.findings = out.findings[: self.MAX_STATEMENTS]
        out.limitations = out.limitations[: self.MAX_STATEMENTS]
        return out

    @staticmethod
    def _add_entity(store: dict[str, Item], name: str, chunk: Chunk, sentence: str) -> None:
        key = slug(name)
        if key and key not in store:
            store[key] = Item(name, chunk.id, sentence)

    @staticmethod
    def _dedupe_methods(items: list[Item]) -> list[Item]:
        """Drop generic terms subsumed by a more specific one (e.g. 'Language Model' vs 'Protein Language Model')."""
        names = [slug(i.text) for i in items]
        keep = []
        for item, key in zip(items, names):
            if any(other != key and other.endswith(key) and len(other) > len(key) for other in names):
                continue
            keep.append(item)
        return keep


# --------------------------------------------------------------------------- Claude

def _item_schema(with_kind: bool = False) -> dict:
    props = {
        "text": {"type": "string", "description": "Name (for methods/datasets) or a concise self-contained statement."},
        "chunk_id": {"type": "string", "description": "Id of the chunk that supports this item."},
        "quote": {"type": "string", "description": "Exact sentence copied verbatim from that chunk."},
    }
    required = ["text", "chunk_id", "quote"]
    if with_kind:
        props["kind"] = {"type": "string", "enum": ["limitation", "future_work"]}
        required.append("kind")
    return {"type": "array", "items": {"type": "object", "properties": props, "required": required, "additionalProperties": False}}


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "methods": _item_schema(),
        "datasets": _item_schema(),
        "claims": _item_schema(),
        "findings": _item_schema(),
        "limitations": _item_schema(with_kind=True),
    },
    "required": ["methods", "datasets", "claims", "findings", "limitations"],
    "additionalProperties": False,
}

EXTRACTION_PROMPT = """You are building a scientific knowledge graph. Extract structured knowledge from the paper below.

Definitions:
- methods: techniques, models, algorithms or architectures the paper proposes, uses or compares against. Use the canonical general name (e.g. "Graph Attention Network", not "our 4-head GAT encoder"); include the paper's own named model too.
- datasets: datasets or benchmarks used for training or evaluation.
- claims: the paper's central arguments or conclusions (what the authors assert).
- findings: concrete empirical results, ideally with numbers.
- limitations: stated weaknesses, untested settings, or assumptions (kind="limitation"), and stated future work (kind="future_work").

Rules:
- Only include items explicitly supported by the text. Do not use outside knowledge.
- chunk_id must be one of the [chunk_id] markers below; quote must be copied verbatim from that chunk.
- At most 12 items per category. Statements must be understandable without the paper.

Paper title: {title}

{chunks}"""


class ClaudeExtractor:
    name = "claude"

    def __init__(self, llm):
        self.llm = llm

    def extract(self, paper: ParsedPaper) -> Extraction:
        chunk_text = "\n\n".join(f"[{c.id}] (page {c.page}, {c.section})\n{c.text}" for c in paper.chunks)
        response = self.llm.create(
            max_tokens=16000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(title=paper.title, chunks=chunk_text)}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        data = json.loads(text)

        by_id = {c.id: c for c in paper.chunks}
        out = Extraction(extractor=self.name)
        dropped = 0
        for key in ("methods", "datasets", "claims", "findings", "limitations"):
            for raw in data.get(key, []):
                chunk = by_id.get(raw.get("chunk_id", ""))
                if not chunk or not quote_in_chunk(raw.get("quote", ""), chunk.text):
                    dropped += 1  # unverifiable evidence is discarded, never stored
                    continue
                getattr(out, key).append(Item(raw["text"].strip(), chunk.id, raw["quote"].strip(), raw.get("kind", "")))
        if dropped:
            log.info("Dropped %d extracted items whose evidence could not be verified.", dropped)
        return out


def get_extractor(llm=None, prefer_llm: bool = True):
    if prefer_llm and llm is not None:
        return ClaudeExtractor(llm)
    return HeuristicExtractor()
