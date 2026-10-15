"""Two SYNTHETIC papers on a topic unrelated to the drug-target samples (urban beekeeping).

Used by the project-isolation tests: a project holding these must never surface drug-target
evidence, and vice versa. Invented content, not real publications.
"""

from pathlib import Path

from make_sample_pdfs import NOTE, build

BEE_PAPERS = [
    {
        "file": "bees_rooftop_survival.pdf",
        "title": "Rooftop Apiaries and Honeybee Colony Winter Survival in Dense Cities",
        "authors": "Lena Ortiz, Tomas Berg",
        "year": "2022",
        "abstract": ("We monitored 64 rooftop honeybee colonies in three cities over two winters. Colonies with "
                     "windbreak shelters showed higher winter survival than exposed colonies. " + NOTE),
        "sections": [
            ("Methods", ["Hive weight sensors recorded colony weight every hour. We compared sheltered and exposed "
                         "rooftop hives using a mixed-effects survival model."]),
            ("Results", ["Sheltered rooftop colonies survived winter at a rate of 81 percent, compared with 58 percent "
                         "for exposed colonies. Varroa mite load strongly predicted colony loss."]),
            ("Limitations", ["Our study did not evaluate colonies at street level, so ground-level apiaries remain untested. "
                             "The study was limited to three temperate cities."]),
        ],
    },
    {
        "file": "bees_varroa_treatment.pdf",
        "title": "Oxalic Acid Treatment Timing Against Varroa Mites in Urban Beekeeping",
        "authors": "Priya Nair, Jonas Weber",
        "year": "2023",
        "abstract": ("We compared autumn and winter oxalic acid treatments against Varroa mites in 40 urban colonies. "
                     "Winter treatment reduced mite load more than autumn treatment. " + NOTE),
        "sections": [
            ("Methods", ["Mite drop counts on sticky boards measured Varroa load before and after oxalic acid treatment "
                         "in rooftop and garden apiaries."]),
            ("Results", ["Winter oxalic acid treatment reduced Varroa mite load by 92 percent, while autumn treatment "
                         "reduced it by 71 percent."]),
            ("Limitations", ["We did not evaluate colonies at street level, and ground-level urban apiaries were excluded. "
                             "Effects on queen health were not assessed."]),
        ],
    },
]


def make_bee_pdfs(out_dir) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return [build(p, out) for p in BEE_PAPERS]
