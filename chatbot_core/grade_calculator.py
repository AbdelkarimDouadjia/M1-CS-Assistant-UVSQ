"""Deterministic grade calculator for the M1 Informatique UVSQ parcours.

The calculator understands the per-parcours BCC mapping documented in the
rentrée slides (AMIS, DataScale, IRS, SeCReTS) and applies the official
validation / compensation rules described in
``data/M1_Info_UVSQ_RAG_cleaned.md``.
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRADE_CONFIG_PATH = PROJECT_ROOT / "data" / "grade_config.json"

PARCOURS_LIST: list[str] = ["AMIS", "DataScale", "IRS", "SeCReTS"]
COMPENSATION_THRESHOLD = 7.0
VALIDATION_THRESHOLD = 10.0
MAX_BO_CHOICES = 2

UE_STATUS_ACQUIRED = "acquired"
UE_STATUS_COMPENSABLE = "compensable"
UE_STATUS_BELOW = "below_threshold"
UE_STATUS_MISSING = "missing"

GRADE_KEYWORDS = {
    "moyenne",
    "moyen",
    "semester",
    "semestre",
    "note",
    "notes",
    "grade",
    "grades",
    "calculate",
    "calcul",
    "calculer",
    "moy",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class UE:
    name: str
    code: str
    semester: int
    bcc: str
    ects: float
    rule: str

    @property
    def has_cc(self) -> bool:
        return self.rule != "exam_only"

    @property
    def has_exam(self) -> bool:
        return self.rule not in {"cc_only_no_s2", "cc_only"}

    @property
    def session_2_available(self) -> bool:
        return self.rule != "cc_only_no_s2"


@dataclass
class GradeEntry:
    ue: UE
    final_note: float | None
    cc: float | None
    exam: float | None
    mode: str  # "final" | "cc_et" | "missing"
    formula: str
    status: str

    @property
    def is_present(self) -> bool:
        return self.final_note is not None


@dataclass
class BCCResult:
    name: str
    entries: list[GradeEntry]
    average: float | None
    weight: float
    acquired: bool


@dataclass
class GradeReport:
    parcours: str
    semester: str  # "S1" | "S2" | "year"
    entries: list[GradeEntry]
    bcc_results: list[BCCResult]
    semester_average: float | None
    group_results: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    selected_bo_codes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------


def _default_config() -> dict[str, Any]:
    return {
        "parcours": PARCOURS_LIST,
        "compensation_threshold": COMPENSATION_THRESHOLD,
        "validation_threshold": VALIDATION_THRESHOLD,
        "max_bo_choices": MAX_BO_CHOICES,
        "compensation_groups": [
            {"label": "SF1 + CCB", "blocks": ["SF1", "CCB"], "threshold": 10.0},
            {"label": "SF2 + BO + CCT", "blocks": ["SF2", "BO", "CCT"], "threshold": 10.0},
        ],
        "non_compensable_blocks": ["SF1", "SF2"],
        "ues": [],
    }


def load_config() -> dict[str, Any]:
    if not GRADE_CONFIG_PATH.exists():
        return _default_config()
    try:
        data = json.loads(GRADE_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_config()
    base = _default_config()
    if isinstance(data, dict):
        base.update({k: v for k, v in data.items() if v is not None})
    return base


def load_grade_config() -> list[dict[str, Any]]:
    """Backwards-compatible accessor: returns the raw UE list."""
    config = load_config()
    return list(config.get("ues", []))


def _bcc_for_parcours(ue_raw: dict[str, Any], parcours: str) -> str:
    mapping = ue_raw.get("bcc_by_parcours") or {}
    if isinstance(mapping, dict) and parcours in mapping:
        return str(mapping[parcours])
    return str(ue_raw.get("bcc", "Inconnu"))


def all_ues(parcours: str) -> list[UE]:
    parcours = _canonical_parcours(parcours) or parcours
    config = load_config()
    return [
        UE(
            name=str(item.get("name", "")),
            code=str(item.get("code", "")),
            semester=int(item.get("semester", 1)),
            bcc=_bcc_for_parcours(item, parcours),
            ects=float(item.get("ects", 3)),
            rule=str(item.get("rule", "cc_et")),
        )
        for item in config.get("ues", [])
    ]


def build_program(
    parcours: str,
    semester: str,
    selected_bo_codes: Iterable[str] | None = None,
) -> list[UE]:
    """Return the list of UEs the student must take for ``semester``.

    ``semester`` is ``"S1"``, ``"S2"`` or ``"year"``. For ``"S2"``/``"year"``
    BO modules are kept only when explicitly chosen (or all of them when the
    student has not chosen yet, which surfaces the picker in the UI).
    """
    parcours = _canonical_parcours(parcours) or parcours
    ues = all_ues(parcours)
    semester_key = (semester or "").lower()
    if semester_key in {"s1", "1", "semester 1", "semestre 1"}:
        return [ue for ue in ues if ue.semester == 1]
    s2_ues = [ue for ue in ues if ue.semester == 2]
    if selected_bo_codes is not None:
        selected = {code.strip() for code in selected_bo_codes if code}
        s2_ues = [ue for ue in s2_ues if ue.bcc != "BO" or ue.code in selected]
    if semester_key in {"s2", "2", "semester 2", "semestre 2"}:
        return s2_ues
    if semester_key in {"year", "annee", "année", "all", "tout"}:
        return [ue for ue in ues if ue.semester == 1] + s2_ues
    return ues


def bo_options(parcours: str) -> list[UE]:
    parcours = _canonical_parcours(parcours) or parcours
    return [ue for ue in all_ues(parcours) if ue.bcc == "BO" and ue.semester == 2]


# ---------------------------------------------------------------------------
# Parcours inference
# ---------------------------------------------------------------------------


def _canonical_parcours(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    table = {
        "amis": "AMIS",
        "datascale": "DataScale",
        "data scale": "DataScale",
        "irs": "IRS",
        "secrets": "SeCReTS",
        "secret": "SeCReTS",
        "secrests": "SeCReTS",
        "secreets": "SeCReTS",
    }
    return table.get(re.sub(r"[^a-z0-9]+", "", normalized) or normalized)


def infer_parcours(text: str) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    for parcours in PARCOURS_LIST:
        if re.search(rf"\b{re.escape(parcours.lower())}\b", lowered):
            return parcours
    canonical = _canonical_parcours(text)
    return canonical


# ---------------------------------------------------------------------------
# UE final note computation
# ---------------------------------------------------------------------------


def calculate_ue_final(
    ue: UE,
    cc: float | None = None,
    exam: float | None = None,
    final: float | None = None,
    session: int = 1,
) -> GradeEntry:
    """Compute the final note for a single UE.

    ``final`` takes priority. Otherwise the formula depends on the UE rule:

    - ``exam_only`` : note = exam
    - ``cc_only_no_s2`` : note = cc (no session 2)
    - ``cc_s1_exam_s2`` : session 1 = cc; session 2 = exam
    - default ``cc_et`` : note = (cc + 2 × exam) / 3
    """
    if final is not None:
        note = _clamp(final)
        return GradeEntry(
            ue=ue,
            final_note=note,
            cc=cc,
            exam=exam,
            mode="final",
            formula="Note finale renseignée directement",
            status=_status_for(note),
        )

    note: float | None = None
    formula = ""
    if ue.rule == "exam_only":
        if exam is not None:
            note = _clamp(exam)
            formula = "Note = examen écrit (pas de CC)"
    elif ue.rule == "cc_only_no_s2":
        if cc is not None:
            note = _clamp(cc)
            formula = "Note = CC (pas de session 2 pour cette UE)"
    elif ue.rule == "cc_s1_exam_s2":
        if session >= 2 and exam is not None:
            note = _clamp(exam)
            formula = "Session 2 : Note = examen écrit"
        elif cc is not None:
            note = _clamp(cc)
            formula = "Session 1 : Note = CC"
    else:  # cc_et
        if cc is not None and exam is not None:
            note = _clamp((cc + 2 * exam) / 3)
            formula = "Note finale = (CC + 2 × Examen) / 3"
        elif exam is not None and not ue.has_cc:
            note = _clamp(exam)
            formula = "Note = examen (CC indisponible)"

    if note is None:
        return GradeEntry(
            ue=ue,
            final_note=None,
            cc=cc,
            exam=exam,
            mode="missing",
            formula="Note manquante",
            status=UE_STATUS_MISSING,
        )
    return GradeEntry(
        ue=ue,
        final_note=note,
        cc=cc,
        exam=exam,
        mode="cc_et",
        formula=formula,
        status=_status_for(note),
    )


def _clamp(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 20:
        return 20.0
    return round(float(value), 4)


def _status_for(note: float) -> str:
    if note >= VALIDATION_THRESHOLD:
        return UE_STATUS_ACQUIRED
    if note >= COMPENSATION_THRESHOLD:
        return UE_STATUS_COMPENSABLE
    return UE_STATUS_BELOW


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def calculate_report(
    parcours: str,
    entries: list[GradeEntry],
    semester: str = "year",
    selected_bo_codes: Iterable[str] | None = None,
) -> GradeReport:
    parcours_canonical = _canonical_parcours(parcours) or parcours
    config = load_config()
    non_compensable = set(config.get("non_compensable_blocks", ["SF1", "SF2"]))

    by_bcc: dict[str, list[GradeEntry]] = {}
    for entry in entries:
        by_bcc.setdefault(entry.ue.bcc, []).append(entry)

    bcc_results: list[BCCResult] = []
    for name, items in by_bcc.items():
        weight = sum(item.ue.ects for item in items if item.is_present)
        present = [item for item in items if item.is_present]
        if weight > 0 and present:
            avg = sum(item.final_note * item.ue.ects for item in present) / weight  # type: ignore[operator]
            acquired = avg >= VALIDATION_THRESHOLD
        else:
            avg = None
            acquired = False
        bcc_results.append(
            BCCResult(name=name, entries=items, average=avg, weight=weight, acquired=acquired)
        )

    bcc_results.sort(key=lambda block: ("SF1 SF2 CCB BO CCT".split().index(block.name) if block.name in "SF1 SF2 CCB BO CCT".split() else 99))

    total_weight = sum(item.ue.ects for item in entries if item.is_present)
    if total_weight > 0:
        semester_avg = sum(
            (entry.final_note or 0) * entry.ue.ects for entry in entries if entry.is_present
        ) / total_weight
    else:
        semester_avg = None

    group_results: list[dict[str, Any]] = []
    for group in config.get("compensation_groups", []):
        blocks = set(group.get("blocks", []))
        items = [entry for entry in entries if entry.ue.bcc in blocks and entry.is_present]
        if not items:
            continue
        weight = sum(item.ue.ects for item in items)
        avg = sum((item.final_note or 0) * item.ue.ects for item in items) / weight
        group_results.append(
            {
                "label": group.get("label", " + ".join(group.get("blocks", []))),
                "blocks": sorted(blocks),
                "average": avg,
                "threshold": float(group.get("threshold", 10.0)),
                "passed": avg >= float(group.get("threshold", 10.0)),
            }
        )

    warnings: list[str] = []
    for entry in entries:
        if not entry.is_present:
            warnings.append(f"{entry.ue.name} : note manquante, l'UE n'est pas comptée.")
            continue
        if entry.final_note is not None and entry.final_note < COMPENSATION_THRESHOLD:
            warnings.append(
                f"{entry.ue.name} : note ({entry.final_note:.2f}) sous le seuil de compensation 7/20."
            )
    for block in bcc_results:
        if block.name in non_compensable and block.average is not None and not block.acquired:
            warnings.append(
                f"BCC {block.name} : non acquis ({block.average:.2f}/20) et non compensable."
            )
    for group in group_results:
        if not group["passed"]:
            warnings.append(
                f"Groupe {group['label']} sous 10/20 ({group['average']:.2f}) : la compensation entre BCC n'est pas garantie."
            )

    if semester.lower() in {"s2", "2", "year", "annee", "année"} and selected_bo_codes is not None:
        bo_count = len([code for code in selected_bo_codes if code])
        if bo_count != int(config.get("max_bo_choices", MAX_BO_CHOICES)):
            warnings.append(
                f"Le S2 demande exactement {config.get('max_bo_choices', MAX_BO_CHOICES)} UEs BO sélectionnées (vous en avez {bo_count})."
            )

    return GradeReport(
        parcours=parcours_canonical,
        semester=semester,
        entries=entries,
        bcc_results=bcc_results,
        semester_average=semester_avg,
        group_results=group_results,
        warnings=warnings,
        selected_bo_codes=list(selected_bo_codes or []),
    )


def format_report(report: GradeReport) -> tuple[str, str]:
    """Render a Markdown summary of the report (response body, details)."""
    lines: list[str] = []
    label_semester = {"s1": "S1", "s2": "S2", "year": "Année", "annee": "Année", "année": "Année"}
    label = label_semester.get(report.semester.lower(), report.semester or "Année")
    if report.semester_average is not None:
        lines.append(f"### Moyenne {label} ({report.parcours}) : {report.semester_average:.2f}/20")
    else:
        lines.append(f"### Moyenne {label} ({report.parcours}) : non calculable")
    lines.append("")
    lines.append("| UE | BCC | Mode | Note | Statut |")
    lines.append("|---|---|---|---:|---|")
    status_label = {
        UE_STATUS_ACQUIRED: "Acquise",
        UE_STATUS_COMPENSABLE: "Compensable (≥7)",
        UE_STATUS_BELOW: "Sous 7/20",
        UE_STATUS_MISSING: "Manquante",
    }
    for entry in report.entries:
        note_str = f"{entry.final_note:.2f}" if entry.final_note is not None else "—"
        mode_str = {
            "final": "note finale",
            "cc_et": entry.formula or "(CC + 2×ET)/3",
            "missing": "—",
        }.get(entry.mode, entry.mode)
        lines.append(
            f"| {entry.ue.name} | {entry.ue.bcc} | {mode_str} | {note_str} | {status_label.get(entry.status, entry.status)} |"
        )
    lines.append("")
    lines.append("### BCC")
    for block in report.bcc_results:
        if block.average is None:
            lines.append(f"- **{block.name}** : pas de note disponible.")
            continue
        suffix = "acquis" if block.acquired else "non acquis"
        lines.append(f"- **{block.name}** : {block.average:.2f}/20 ({suffix})")
    if report.group_results:
        lines.append("")
        lines.append("### Compensation entre BCC")
        for group in report.group_results:
            status = "OK" if group["passed"] else "À surveiller"
            lines.append(f"- {group['label']} : {group['average']:.2f}/20 ({status})")
    if report.warnings:
        lines.append("")
        lines.append("### Points d'attention")
        for warning in report.warnings:
            lines.append(f"- {warning}")
    lines.append("")
    lines.append(
        "_Cette estimation utilise les règles du règlement intérieur. Le jury et le relevé de notes officiel restent seuls juges._"
    )
    details = (
        f"Parcours: {report.parcours}. Période: {label}. "
        f"UEs renseignées: {sum(1 for entry in report.entries if entry.is_present)}/{len(report.entries)}."
    )
    return "\n".join(lines), details


# ---------------------------------------------------------------------------
# Chat-driven entry point
# ---------------------------------------------------------------------------


_INTENT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"calcule\w*\s+(?:moi\s+)?(?:ma\s+|mon\s+|le\s+|la\s+)?moy",
        r"calc\w*\s+(?:ma\s+|mon\s+)?(?:moyenne|moy|note)",
        r"calculer\s+(?:ma\s+|mon\s+)?moyenne",
        r"calculer\s+(?:ma\s+|mon\s+)?moy",
        r"calculer\s+(?:ma\s+|mon\s+)?(?:semestre|notes?)",
        r"estimer?\s+(?:ma\s+|mon\s+)?moy",
        r"\b(?:aide(?:r|z)?|help)\b.*\b(?:moy(?:enne)?|note|grade|average|gpa)\b",
        r"\b(?:moy(?:enne)?|note|grade|average|gpa)\b.*\b(?:aide(?:r|z)?|help)\b",
        r"compute\s+(?:my\s+)?(?:average|gpa|grade)",
        r"calculate\s+(?:my\s+)?(?:average|gpa|grade)",
        r"what(?:'s| is)\s+my\s+(?:average|gpa|grade)",
        r"je\s+veux\s+(?:savoir|calculer|connaitre|connaître).*\bmoy",
        r"(?:peux[- ]tu|pouvez[- ]vous|peux\s+stp).*\b(?:calculer|estimer|aider)\b.*\bmoy",
        r"\bmoy(?:enne)?\b.*\b(?:semestre|s1|s2|annee|année)\b",
        r"\b(?:semestre|s1|s2|annee|année)\b.*\bmoy",
    )
]


def is_grade_query(text: str) -> bool:
    """True when the message contains explicit `UE : note` pairs to compute."""
    lowered = text.lower()
    random_requested = any(word in lowered for word in {"random", "aléatoire", "aleatoire", "hasard"})
    has_note_pair = bool(_extract_notes(text))
    return any(keyword in lowered for keyword in GRADE_KEYWORDS) and (has_note_pair or random_requested)


def is_grade_intent(text: str) -> bool:
    """True when the user *intends* to compute a grade but hasn't typed notes.

    Examples that match:
    - "svp esq tu peux aider moi calculer mon moyenne de semestre 1"
    - "Calcule ma moyenne"
    - "help me compute my GPA"
    - "je veux estimer ma moyenne"

    Messages with actual `UE : note` pairs are intentionally excluded so the
    text-only path (``is_grade_query``) keeps working.
    """
    if not text:
        return False
    if is_grade_query(text):
        return False
    return any(pattern.search(text) for pattern in _INTENT_PATTERNS)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).strip()


def _fold_for_matching(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


_UE_ALIAS_HINTS: dict[str, set[str]] = {
    "MIN17101": {"math", "maths", "mathematiques", "maths discretes", "mathematiques discretes"},
    "MIN17102": {"complement algo", "algo complexite", "algorithmique complexite", "complexite"},
    "MIN17103": {"complement prog", "complement programmation", "programmation s1"},
    "MIN15111": {"ro", "recherche operationnelle", "algorithmique randomisee", "algo randomisee"},
    "MIN15112": {"reseau", "reseaux", "reseaux systemes", "systemes reseaux"},
    "MIN15113": {"bd", "bdd", "base de donnees", "bases de donnees", "database"},
    "MIN15121": {"graphe", "graphes", "algorithmique graphes", "theorie des graphes"},
    "MIN15122": {"crypto", "cryptographie"},
    "MIN17211": {"ranking", "methodes ranking", "methodes de ranking"},
    "MIN17212": {"simulation"},
    "MIN17213": {"tuning bd", "tuning de bd", "tuning base de donnees"},
    "MIN17214": {"conception bd", "conception de bd", "conception base de donnees"},
    "MIN17215": {"protocoles ip", "protocole ip", "ip"},
    "MIN17216": {"reseaux etendus", "wan"},
    "MIN17217": {"application web", "web securite", "application web securite"},
    "MIN17218": {"calcul securise"},
    "MIN18000": {"evry", "analyse donnees", "analyse des donnees"},
    "MSANGS2I": {"anglais", "english"},
    "MIN17201": {"programmation gl preuve", "gl preuve", "preuve", "programmation s2"},
    "MIN15221": {"ter"},
}


def _ue_aliases(ue: UE) -> set[str]:
    aliases = {
        _normalize_text(ue.name),
        _normalize_text(ue.code),
    }
    aliases.update(_UE_ALIAS_HINTS.get(ue.code, set()))
    return {alias for alias in aliases if alias}


def _extract_notes(text: str) -> list[tuple[str, float]]:
    pattern = re.compile(
        r"(?P<label>[A-Za-zÀ-ÿ0-9'’/ ._-]{3,80}?)\s*(?:[:=]|->|:)\s*(?P<note>\d{1,2}(?:[,.]\d+)?)",
        re.IGNORECASE,
    )
    notes: list[tuple[str, float]] = []
    seen: set[tuple[str, float]] = set()

    def _push(label: str, note: float) -> None:
        if not (0 <= note <= 20):
            return
        label = label.strip(" ,;.\n\t")
        if not label:
            return
        key = (_normalize_text(label), round(note, 3))
        if key in seen:
            return
        seen.add(key)
        notes.append((label, note))

    for match in pattern.finditer(text):
        note = float(match.group("note").replace(",", "."))
        _push(match.group("label"), note)

    folded = _fold_for_matching(text)
    known_ues = all_ues(PARCOURS_LIST[0])
    for ue in known_ues:
        aliases = sorted(_ue_aliases(ue), key=len, reverse=True)
        for alias in aliases:
            escaped = re.escape(alias).replace(r"\ ", r"\s+")
            boundary = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
            patterns = [
                re.compile(rf"{boundary}\s*(?:[:=]|->)?\s*(?P<note>\d{{1,2}}(?:[,.]\d+)?)(?:\s*/\s*20)?"),
                re.compile(rf"(?P<note>\d{{1,2}}(?:[,.]\d+)?)(?:\s*/\s*20)?\s*(?:en|a|à|pour|dans)\s+{boundary}"),
            ]
            for alias_pattern in patterns:
                for match in alias_pattern.finditer(folded):
                    note = float(match.group("note").replace(",", "."))
                    _push(ue.name, note)
    return notes


def _find_ue(label: str, ues: list[UE]) -> UE | None:
    normalized_label = _normalize_text(label)
    best: tuple[int, UE] | None = None
    for ue in ues:
        candidates = list(_ue_aliases(ue))
        score = 0
        for candidate in candidates:
            if candidate and candidate in normalized_label:
                score = max(score, len(candidate))
            elif normalized_label and normalized_label in candidate:
                score = max(score, len(normalized_label))
        if score and (best is None or score > best[0]):
            best = (score, ue)
    return best[1] if best else None


def _semester_from_question(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(s2|semestre\s*2|semester\s*2)\b", lowered):
        return "s2"
    if re.search(r"\b(s1|semestre\s*1|semester\s*1)\b", lowered):
        return "s1"
    if re.search(r"\b(année|annee|year|annuelle?)\b", lowered):
        return "year"
    return "year"


def _random_demo_entries(ues: list[UE], seed: str) -> list[GradeEntry]:
    rng = random.Random(seed or "demo")
    entries: list[GradeEntry] = []
    for ue in ues:
        entries.append(
            calculate_ue_final(ue, final=round(rng.uniform(7.0, 18.0), 2))
        )
    return entries


def calculate_grade_response(question: str, memory_profile: str = "") -> tuple[str, str]:
    parcours = infer_parcours(question) or infer_parcours(memory_profile)
    if not parcours:
        return (
            "Avant de calculer la moyenne, j'ai besoin de connaître votre parcours "
            "(AMIS, DataScale, IRS ou SeCReTS) car le regroupement des UEs en BCC en dépend. "
            "Indiquez par exemple `Je suis en DataScale` puis reformulez votre demande, "
            "ou utilisez le bouton `Calculer ma moyenne` dans la barre latérale.",
            "Parcours manquant.",
        )

    semester = _semester_from_question(question)
    ues_full = build_program(parcours, semester, selected_bo_codes=None)
    parsed_notes = _extract_notes(question)
    random_demo = False
    if not parsed_notes:
        lowered = question.lower()
        if any(word in lowered for word in {"random", "aléatoire", "aleatoire", "hasard"}):
            random_demo = True
        else:
            return (
                "Je peux calculer une moyenne estimée. Donnez-moi des notes au format "
                "`UE : note` (ex. `Complément d'Algo et Complexité : 17`) ou ouvrez "
                "l'assistant guidé via le bouton `Calculer ma moyenne`.",
                "Aucune note détectée.",
            )

    entries: list[GradeEntry] = []
    if random_demo:
        entries = _random_demo_entries(ues_full, seed=_normalize_text(question))
    else:
        used_codes: set[str] = set()
        for label, note in parsed_notes:
            ue = _find_ue(label, ues_full)
            if ue is None:
                continue
            if ue.code in used_codes:
                continue
            used_codes.add(ue.code)
            entries.append(calculate_ue_final(ue, final=note))
        for ue in ues_full:
            if ue.code in used_codes:
                continue
            entries.append(
                GradeEntry(
                    ue=ue,
                    final_note=None,
                    cc=None,
                    exam=None,
                    mode="missing",
                    formula="Note non fournie",
                    status=UE_STATUS_MISSING,
                )
            )

    selected_bo = [
        entry.ue.code for entry in entries if entry.ue.bcc == "BO" and entry.is_present
    ] if semester in {"s2", "year"} else []
    report = calculate_report(parcours, entries, semester=semester, selected_bo_codes=selected_bo)
    body, details = format_report(report)
    if random_demo:
        body = "_Les notes ci-dessous sont fictives (démonstration)._\n\n" + body
        details += " Mode démonstration aléatoire."
    return body, details
