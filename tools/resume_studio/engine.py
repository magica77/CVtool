"""Evidence-preserving resume selection and transparent lexical JD matching."""
import copy
import re
import unicodedata


# Deliberately narrow equivalences: related technologies are not interchangeable.
TERMS = {
    "Python": [], "SQL": [], "Java": [], "Scala": [], "Go": ["Golang"],
    "C++": [], "C#": [], ".NET": [], "TypeScript": [], "JavaScript": [],
    "AWS": ["Amazon Web Services"], "GCP": ["Google Cloud Platform", "Google Cloud"],
    "Azure": ["Microsoft Azure"], "Kafka": ["Apache Kafka"],
    "Spark": ["Apache Spark"], "Flink": ["Apache Flink"],
    "Airflow": ["Apache Airflow"], "dbt": [], "Snowflake": [], "Databricks": [],
    "Iceberg": ["Apache Iceberg"], "Delta Lake": [], "BigQuery": [],
    "PostgreSQL": ["Postgres"], "MySQL": [], "Redis": [], "DynamoDB": [],
    "Kubernetes": ["K8s"], "Docker": [], "Terraform": [],
    "CI/CD": ["continuous integration and continuous delivery"],
    "CDC": ["change data capture"], "ETL": ["extract transform load"],
    "ELT": ["extract load transform"], "RAG": ["retrieval-augmented generation", "retrieval augmented generation"],
    "LLM": ["large language model", "large language models", "LLMs"],
    "machine learning": ["ML"], "MLOps": [], "PyTorch": [], "TensorFlow": [],
    "LangChain": [], "LangGraph": [], "vector search": [], "embeddings": [],
    "distributed systems": [], "streaming": [], "data modeling": ["data modelling"],
    "data quality": [], "data governance": [], "observability": [],
    "evaluation": ["evaluations"], "agents": ["AI agents", "agentic"],
    "architecture": [], "technical strategy": [], "mentoring": ["mentorship", "mentored"],
    "stakeholder management": [], "customer-facing": ["customer facing"],
    "system design": [], "data platform": ["data platforms"],
    "reliability": [], "security": [], "cost optimization": [],
}


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def contains(text, phrase):
    # Punctuation-aware boundaries prevent SQL matching NoSQL, Java matching
    # JavaScript, and C++ matching C. Flexible whitespace handles PDF wrapping.
    return bool(re.search(r"(?<![\w+#.])" + re.escape(normalize(phrase)) +
                          r"(?![\w+#])", normalize(text)))


def matches(text, term):
    return any(contains(text, alias) for alias in [term] + TERMS.get(term, []))


def require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t\r" for c in value):
        raise ValueError(f"{label} contains control characters")


def validate(profile):
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object")
    for key in ("name", "headline"):
        require_text(profile.get(key), key)
    for key in ("contact", "summary", "skills", "education", "certifications", "projects"):
        value = profile.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list of strings")
        for entry in value:
            require_text(entry, key)
    if not profile.get("contact"):
        raise ValueError("Provide at least one contact detail")
    if not isinstance(profile.get("experience"), list) or not profile["experience"]:
        raise ValueError("Provide at least one experience entry")
    seen = set()
    for role in profile["experience"]:
        if not isinstance(role, dict):
            raise ValueError("Each experience entry must be an object")
        for key in ("id", "company", "title", "start", "end"):
            require_text(role.get(key), f"experience.{key}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", role["id"]):
            raise ValueError("Role IDs may contain only letters, digits, hyphens, and underscores")
        if role["id"] in seen:
            raise ValueError(f"Duplicate ID: {role['id']}")
        seen.add(role["id"])
        for key in ("start", "end"):
            if key == "end" and role[key] == "Present":
                continue
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", role[key]):
                raise ValueError(f"{role['id']}.{key}: use YYYY-MM or Present for end")
        if role["end"] != "Present" and role["start"] > role["end"]:
            raise ValueError(f"{role['id']}: end date precedes start date")
        if "location" in role and not isinstance(role["location"], str):
            raise ValueError("experience.location must be text")
        if not isinstance(role.get("bullets"), list) or not role["bullets"]:
            raise ValueError(f"{role['id']}: provide at least one bullet")
        for bullet in role["bullets"]:
            if not isinstance(bullet, dict):
                raise ValueError("Each bullet must have id and text")
            for key in ("id", "text"):
                require_text(bullet.get(key), f"bullet.{key}")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", bullet["id"]):
                raise ValueError("Bullet IDs may contain only letters, digits, hyphens, and underscores")
            if bullet["id"] in seen:
                raise ValueError(f"Duplicate ID: {bullet['id']}")
            seen.add(bullet["id"])


def evidence(profile):
    result = {}
    for section in ("summary", "skills", "education", "certifications", "projects"):
        for index, value in enumerate(profile.get(section, [])):
            result[f"{section}:{index + 1}"] = value
    for role in profile["experience"]:
        result[role["id"]] = " | ".join(role.get(k, "") for k in ("company", "title", "start", "end", "location"))
        for bullet in role["bullets"]:
            result[bullet["id"]] = bullet["text"]
    return result


def jd_terms(jd, extra=()):
    require_text(jd, "Job description")
    terms = [term for term in TERMS if matches(jd, term)]
    for term in extra:
        require_text(term, "Custom term")
        if term in terms:
            continue
        if not contains(jd, term):
            raise ValueError(f"Custom term does not appear in JD: {term}")
        if not any(normalize(term) == normalize(alias) for existing in terms
                   for alias in [existing] + TERMS.get(existing, [])):
            terms.append(term)
    return terms


def rank_score(text, terms):
    return sum(matches(text, term) for term in terms)


def tailor(profile, jd, title, company, max_bullets=5, extra=()):
    validate(profile)
    require_text(title, "Target title")
    require_text(company, "Target company")
    if max_bullets < 1:
        raise ValueError("max-bullets must be at least 1")
    terms = jd_terms(jd, extra)
    resume = copy.deepcopy(profile)
    # Stable sorts preserve original order on ties. No employer/title rewriting.
    for key in ("skills", "summary"):
        resume[key] = sorted(profile.get(key, []), key=lambda t: -rank_score(t, terms))
    resume["summary"] = resume["summary"][:3]
    resume["experience"].sort(key=lambda r: (r["end"] == "Present", r["end"], r["start"]), reverse=True)
    for role in resume["experience"]:
        role["bullets"] = sorted(role["bullets"], key=lambda b: -rank_score(b["text"], terms))[:max_bullets]
    return {"version": 1, "target": {"title": title, "company": company},
            "job_description": jd, "terms": terms, "source_profile": copy.deepcopy(profile),
            "resume": resume}


def analysis(draft):
    validate(draft["resume"])
    validate(draft["source_profile"])
    source = evidence(draft["source_profile"])
    selected = evidence(draft["resume"])
    terms = draft["terms"]
    rows = []
    for term in terms:
        phrases = [term] + TERMS.get(term, [])
        jd_phrases = [p for p in phrases if contains(draft["job_description"], p)]
        refs = [key for key, value in selected.items() if matches(value, term)]
        source_refs = [key for key, value in source.items() if matches(value, term)]
        bullet_ids = {b["id"] for role in draft["resume"]["experience"] for b in role["bullets"]}
        experience_refs = [key for key in refs if key in bullet_ids or key.startswith("projects:")]
        rows.append({"term": term, "jd_phrases": jd_phrases, "evidence": refs,
                     "source_evidence": source_refs, "experience_evidence": experience_refs,
                     "exact_phrase": any(contains(value, p) for value in selected.values() for p in jd_phrases),
                     "status": "included" if refs else "available but omitted" if source_refs else "not evidenced"})
    changes = []
    for key in ("name", "headline", "contact"):
        if draft["resume"].get(key) != draft["source_profile"].get(key):
            changes.append(f"{key}: changed from master; verify manually")
    # Reordering pooled strings changes their indices, so compare content there.
    for key, value in selected.items():
        if key.split(":")[0] in ("summary", "skills", "education", "certifications", "projects"):
            known = value in draft["source_profile"].get(key.split(":")[0], [])
        else:
            known = source.get(key) == value
        if not known:
            changes.append(f"{key}: new or rewritten claim; compare against source and approve")
    requirements = [line.strip(" -•\t") for line in draft["job_description"].splitlines()
                    if re.search(r"\b(required|must|minimum|preferred|years|degree|travel|onsite|on-site|authorization|clearance)\b", line, re.I)]
    return {"terms": rows, "changed_claims": changes, "requirements_to_review": requirements,
            "evidence": selected, "source_evidence": source,
            "omitted_bullets": [b["id"] for role in draft["source_profile"]["experience"]
                                for b in role["bullets"] if b["id"] not in selected]}
