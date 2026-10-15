"""Generate three small SYNTHETIC research papers for demos and tests.

They are invented examples (not real publications) on one shared topic, written so
the graph has overlapping methods/datasets, a conflicting claim, and open limitations.

Usage:  python scripts/make_sample_pdfs.py [output_dir]
"""

import sys
from pathlib import Path

from reportlab import rl_config
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

rl_config.invariant = 1  # byte-identical output on every run, so paper ids stay stable

NOTE = "Synthetic demo paper generated for ResearchMind AI testing. Not a real publication."

PAPERS = [
    {
        "file": "sample_gat_dti.pdf",
        "title": "Graph Attention Networks for Drug-Target Interaction Prediction",
        "authors": "Maya Chen, Arjun Patel",
        "year": "2023",
        "abstract": (
            "Predicting drug-target interactions is a central step in computational drug discovery. "
            "We propose DTI-GAT, a model that applies a Graph Attention Network to molecular graphs and "
            "combines it with a convolutional neural network over protein sequences. "
            "We show that attention over molecular substructures improves interaction prediction. "
            "On the DAVIS dataset, DTI-GAT achieves an AUC of 0.91, outperforming the DeepDTA baseline by 4%."
        ),
        "sections": [
            ("1 Introduction", [
                "Drug discovery pipelines rely on screening large compound libraries against protein targets. "
                "Existing deep learning models such as DeepDTA encode drugs as strings and ignore molecular topology. "
                "We argue that graph-structured representations of molecules capture binding-relevant chemistry better than string encodings.",
            ]),
            ("2 Method", [
                "DTI-GAT represents each drug as a molecular graph where atoms are nodes and bonds are edges. "
                "A Graph Attention Network with four attention heads produces atom embeddings, which are pooled into a drug vector. "
                "Protein sequences are encoded with a convolutional neural network. The two vectors are concatenated and passed to a multilayer perceptron.",
            ]),
            ("3 Experiments", [
                "We evaluate on the DAVIS dataset, which contains kinase inhibitor binding measurements, and on BindingDB. "
                "We use a random split with 80% training, 10% validation and 10% test data.",
                "Results show that DTI-GAT achieves an AUC of 0.91 on DAVIS and 0.88 on BindingDB. "
                "Attention-based graph models generalize well to unseen proteins in our experiments, improving accuracy by 3% on held-out targets.",
            ]),
            ("4 Limitations", [
                "Our evaluation is limited to kinase targets from DAVIS and BindingDB. "
                "We did not evaluate a cold-start setting in which test proteins are completely unseen during training. "
                "The model ignores three-dimensional protein structure.",
                "Future work should evaluate DTI-GAT on the KIBA dataset and on cold-start protein splits.",
            ]),
            ("5 Conclusion", [
                "We presented DTI-GAT, demonstrating that graph attention over molecular structure improves drug-target interaction prediction.",
            ]),
        ],
    },
    {
        "file": "sample_plm_coldstart.pdf",
        "title": "Protein Language Models Improve Cold-Start Drug-Target Prediction",
        "authors": "Sofia Rossi, Daniel Okafor",
        "year": "2024",
        "abstract": (
            "Generalizing to proteins never seen during training remains difficult for drug-target interaction models. "
            "We introduce PLM-DTI, which uses a pretrained protein language model (ESM-2) with contrastive learning to align drug and protein embeddings. "
            "We find that attention-based graph models do not generalize to unseen proteins, while protein language model features do. "
            "PLM-DTI improves cold-start AUC by 7% on the KIBA dataset."
        ),
        "sections": [
            ("1 Introduction", [
                "Most drug-target interaction benchmarks use random splits that leak protein information between training and test sets. "
                "In realistic discovery settings, the target protein is often novel. "
                "We show that cold-start evaluation exposes a large performance drop for graph-based models.",
            ]),
            ("2 Method", [
                "PLM-DTI encodes proteins with the ESM-2 protein language model and drugs with a graph neural network. "
                "A contrastive learning objective pulls interacting drug-protein pairs together in a shared embedding space. "
                "We also compare against a Graph Attention Network baseline and a Transformer baseline.",
            ]),
            ("3 Results", [
                "We evaluate on the DAVIS dataset and the KIBA dataset using cold-start protein splits. "
                "Results show that PLM-DTI reaches an AUC of 0.84 on cold-start KIBA, a 7% improvement over the Graph Attention Network baseline. "
                "The Graph Attention Network baseline drops from 0.90 AUC on random splits to 0.71 AUC on cold-start splits, "
                "indicating that attention-based graph models do not generalize to unseen proteins.",
            ]),
            ("4 Limitations", [
                "PLM-DTI has a high computational cost because the protein language model requires large GPU memory. "
                "The approach does not use three-dimensional structural information about binding pockets. "
                "It remains unclear whether combining language model features with protein structure would further improve cold-start performance.",
            ]),
            ("5 Conclusion", [
                "Protein language models provide transferable representations that substantially improve cold-start drug-target prediction.",
            ]),
        ],
    },
    {
        "file": "sample_structure_gnn.pdf",
        "title": "Structure-Aware Graph Neural Networks for Binding Affinity Estimation",
        "authors": "Lena Fischer, Haruto Sato",
        "year": "2024",
        "abstract": (
            "Binding affinity estimation benefits from knowledge of the three-dimensional protein-ligand complex. "
            "We propose SA-GNN, a graph neural network that operates on 3D protein-ligand interaction graphs. "
            "We demonstrate that incorporating 3D structure improves affinity prediction. "
            "On the PDBbind dataset, SA-GNN reduces RMSE by 12% compared to sequence-based models."
        ),
        "sections": [
            ("1 Introduction", [
                "Sequence-based affinity models ignore the geometry of binding pockets. "
                "We argue that explicit 3D structure is necessary for accurate affinity estimation.",
            ]),
            ("2 Method", [
                "SA-GNN builds an interaction graph from the protein-ligand complex, connecting atoms within 5 angstroms. "
                "Message passing is performed with a Graph Attention Network layer followed by an equivariant graph neural network layer.",
            ]),
            ("3 Experiments", [
                "We train and evaluate on the PDBbind dataset core set and additionally test on BindingDB complexes with docked poses. "
                "Results show that SA-GNN achieves an RMSE of 1.21, a 12% reduction compared to DeepDTA, and a Pearson correlation of 0.83.",
            ]),
            ("4 Limitations", [
                "SA-GNN requires experimentally resolved or docked 3D structures, which are unavailable for many targets. "
                "We did not evaluate on cold-start protein splits or on the DAVIS and KIBA benchmarks. "
                "Performance with predicted structures from AlphaFold remains untested.",
            ]),
            ("5 Conclusion", [
                "Structure-aware message passing improves binding affinity estimation when 3D complexes are available.",
            ]),
        ],
    },
]


def build(paper: dict, out_dir: Path) -> Path:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Title"], fontSize=20, leading=24)
    small = ParagraphStyle("S", parent=styles["Normal"], fontSize=8, textColor="#666666")
    path = out_dir / paper["file"]
    doc = SimpleDocTemplate(
        str(path), pagesize=letter, title=paper["title"], author=paper["authors"],
        subject=NOTE, creator="ResearchMind sample generator",
    )
    story = [
        Paragraph(paper["title"], title_style),
        Paragraph(paper["authors"], styles["Normal"]),
        Paragraph(f"Preprint, {paper['year']}", styles["Normal"]),
        Paragraph(NOTE, small),
        Spacer(1, 12),
        Paragraph("Abstract", styles["Heading2"]),
        Paragraph(paper["abstract"], styles["Normal"]),
    ]
    for i, (heading, paragraphs) in enumerate(paper["sections"]):
        if i == 2:
            story.append(PageBreak())  # multi-page PDFs exercise page tracking
        story.append(Paragraph(heading, styles["Heading2"]))
        for para in paragraphs:
            story.append(Paragraph(para, styles["Normal"]))
            story.append(Spacer(1, 6))
    story += [Paragraph("References", styles["Heading2"]),
              Paragraph("[1] Placeholder reference for the synthetic paper.", styles["Normal"])]
    doc.build(story)
    return path


def main(out_dir: str | None = None) -> list[Path]:
    target = Path(out_dir) if out_dir else Path(__file__).resolve().parents[2] / "data" / "papers"
    target.mkdir(parents=True, exist_ok=True)
    return [build(p, target) for p in PAPERS]


if __name__ == "__main__":
    for p in main(sys.argv[1] if len(sys.argv) > 1 else None):
        print(f"wrote {p}")
