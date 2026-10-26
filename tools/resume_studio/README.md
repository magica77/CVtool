# Resume Studio

Turn a reusable master resume and a job description into a professional,
evidence-backed application draft. Runs locally with Python 3.9+; the core
tool requires no packages, API key, account, or network connection.

## Use it with this agent

Put your resume and the complete job description in this workspace, then ask:

> Use tools/resume_studio to import my resume at [path]. Build my master
> profile from the original, flag missing information, and let me review it.

Once the master is accurate:

> Tailor my master profile to [JD path] for [company and title]. Rewrite the
> summary and relevant bullets using only my verified experience, show me
> the gaps and changed claims, and export professional Word and PDF drafts.

The agent does the writing using `editing-prompt.md`; the executable selects
existing evidence, checks structure, tracks edits, and renders documents.
It does not call an LLM or invent resume claims. Candidate approval is still
needed for final claims and application submission.

## Try the fictional example

From the repository root:

```bash
python3 tools/resume_studio/resume.py tailor \
  --profile tools/resume_studio/examples/profile.json \
  --jd tools/resume_studio/examples/job.txt \
  --title "Principal Data Platform Engineer" \
  --company "Meridian Labs" \
  --out tools/resume_studio/output/my-demo
```

Open `output/my-demo/resume.html` in your browser. The preview includes a
**Print / Save PDF** button. Choose Letter paper, disable browser headers and
footers, and check page breaks. The print stylesheet removes preview controls.
`resume.docx` is directly editable in Word or LibreOffice.

Example names, employers, metrics, and the JD are fictional and must never be
used as your own experience.

## Import once

```bash
python3 tools/resume_studio/resume.py prepare \
  --source /path/to/my-resume.docx \
  --out tools/resume_studio/private/master
```

This creates extracted `source.txt`, a blank `profile.json`, and an
`import-prompt.md` for the agent. It intentionally does not guess structure or
turn missing details into facts. Ask the agent to fill the profile using the
source, then check it against your original resume. The blank profile will not
validate until populated.

Accepted source formats: UTF-8 `.txt` / `.md`, `.docx`, and text-based `.pdf`.
PDF **import** needs `pdftotext` or the optional `pypdf` Python package; neither
is needed for DOCX/TXT import. Scans need separate OCR. DOCX extraction reads
body paragraphs and tables, but not headers, footers, or hyperlink targets
that are not visible text. Review contact information and reading order.

The example profile documents the schema. Summary is a pool of independently
readable, supported sentences; the tool selects at most three. Skills,
education, certifications, and projects are string lists. Each role and bullet
needs a unique ID using letters, digits, hyphens, or underscores. Dates use
`YYYY-MM`, with `Present` allowed as an end date. Missing dates must be clarified,
not fabricated. Optional sections may be omitted or empty.

```bash
python3 tools/resume_studio/resume.py validate \
  --profile tools/resume_studio/private/master/profile.json
```

## Tailor for each job

Save the full current JD as a local text file. The tool also accepts the same
document formats as `prepare`; it does not fetch job URLs.

```bash
python3 tools/resume_studio/resume.py tailor \
  --profile tools/resume_studio/private/master/profile.json \
  --jd tools/resume_studio/private/job.txt \
  --title "Principal Data Engineer" \
  --company "Target Company" \
  --max-bullets 5 \
  --term "platform migration" \
  --out tools/resume_studio/output/target-company-v1
```

Use `--term` only for a phrase actually present in that JD. Repeat it to cover
specialized tools or responsibilities beyond the built-in AI/data vocabulary.

The tool reorders skills, summary sentences, and bullets by recognized JD term
coverage, keeping at most the requested bullets **per role**. It preserves
reverse employment chronology, all jobs, and original claims. It does not
automatically rewrite the professional headline to the target title; the
agent can propose a truthful headline during editing. Older jobs and optional
sections can be condensed by editing the draft after review.

| Output | Purpose |
| --- | --- |
| `resume.docx` | Single-column Word resume with real text and bullets |
| `resume.html` | Professional preview and print-to-PDF layout |
| `resume.txt` | Plain-text reference / application-field copy |
| `draft.json` | Editable resume plus unchanged master and JD context |
| `review.md` | Evidence matrix, gaps, wording suggestions, edited-claim flags |
| `analysis.json` | Machine-readable matching and master/selected evidence |
| `job-description.txt` | Complete saved JD |
| `editing-prompt.md` | Instructions for grounded agent-assisted rewriting |
| `writing-review.json` | Short-sentence and formulaic-wording diagnostics |
| `reviewer-prompt.md` | Rubric for an independent subagent evaluation |
| `manifest.json` | Draft status, generation time, checks, and file hashes |

Always write a new output directory. Existing directories are never overwritten.
Keep personal files inside `private/` and generated application versions inside
`output/`; both are ignored by the tool's `.gitignore`. The program makes no
external requests. Using an AI agent to edit files is subject to that agent's
own data handling; local operation is not a claim that the AI runs offline.

## Edit and regenerate

Follow `editing-prompt.md`, editing only the `resume` object in `draft.json`.
Keep the source profile, JD, terms, and stable IDs intact for comparison.

```bash
python3 tools/resume_studio/resume.py render \
  --draft tools/resume_studio/output/target-company-v1/draft.json \
  --out tools/resume_studio/output/target-company-v2
```

Reports are recomputed after edits. New or rewritten claims are flagged for
manual review, including changed metrics and historical titles. The tool
cannot establish whether a claim is true. Edits to Word alone are not imported
back into the master or draft.

For automated PDF export, add `--pdf` to `tailor` or `render` when
`agent-browser` and its local browser are installed and allowed to launch.
The tool uses an isolated browser session and closes it afterward. In restricted
agent environments a nested browser process may be blocked even when direct
browser commands work. In that case, omit `--pdf` and use the preview's print
button, or ask the agent to export the preview through its browser tool.

## What the checks mean

Matching is a transparent lexical heuristic, not an employer's ATS or a
semantic qualification assessment. It handles a small explicit alias map
(such as AWS / Amazon Web Services) and avoids substring errors like SQL /
NoSQL. Unsupported terms are flagged, never added to the resume. Alias matches
are distinguished from literal JD phrasing. A skills-list mention is
distinguished from work/project evidence.

The matcher can miss unfamiliar terms and cannot reliably interpret negation,
alternatives, years, or required vs. preferred criteria. The report includes
requirement excerpts for human review; those excerpts are not exhaustive.
There is no claimed ATS pass score or callback guarantee.

Word exports are checked for complete text and reading order on every run.
PDF layout and extraction need a manual check. Copy the PDF into a plain-text
editor and compare with `resume.txt`; follow the employer's requested format.
No hidden keywords, white text, graphics, layout columns, or inflated titles
are used. Aim for readable 1–2 page output; the tool does not shrink fonts to
force a page count.

Research and source assessment: [ATS research](../../docs/resume-tool-research.md).

## Writing style and independent review

Use the user's approximately 80% ASD-STE100 goal as a practical plain-language
standard. Prefer short, direct sentences, active verbs, one main idea, and
consistent terms. Keep exact technical names and true JD keywords. Normal
resume fragments are allowed. Preserve factual meaning over a word limit.
This is an adaptation, not certified STE compliance.

Every new `tailor` or `render` package includes this guidance in the editing
prompt. `writing-review.json` flags approximate sentence lengths over 25 words,
stock phrases, possible passive wording, and repeated bullet openings. It does
not rewrite content, enforce the STE dictionary, or detect AI authorship.

After substantive drafting, the agent must ask an independent subagent to
follow `reviewer-prompt.md`. It scores ATS readiness, natural/specific writing,
professionalism, application strength, and STE-inspired clarity out of 100.
Each score has explicit components, evidence, and limits. Aim for 80 or more
on the internal clarity rubric, without claiming a percentage of STE compliance.

The CLI cannot launch subagents itself. Its review status stays **pending**;
the actual reviewer writes `quality-evaluation.md` with the draft hash. A new
draft needs a fresh review. No reviewer can infer a reliable interview or offer
probability from resume text alone; that field stays unestimated without
relevant calibrated outcome data. Application strength is a judgment, not
a hiring probability.

See the [independent fictional-sample review](../../docs/resume-quality-review.md)
and [writing policy sources](../../docs/resume-writing-policy.md).

## Verification

```bash
python3 -m unittest discover -s tools/resume_studio/tests -v
```

Tests cover evidence preservation, differing JD selections, aliases and token
boundaries, omissions vs. gaps, changed claims, invalid profiles, chronology,
HTML escaping, Unicode Word extraction, clean CLI errors, and atomic output.
