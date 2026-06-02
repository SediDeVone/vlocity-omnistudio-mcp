# Changelog

## [1.0.0] - 2026-05-27

### Added
- Initial release of vlocity-impact-analyzer composite skill
- 5-step intelligent workflow for OmniStudio/Vlocity component impact analysis
- Three analysis modes: `analyze` (default), `blast-radius` (quick risk), `impact-report` (stakeholder format)
- Documentation check with user-permissioned index generation (asks before running `--generate-all`)
- Component identification with fuzzy matching fallback for typos
- Full transitive dependency analysis with journey and flow documentation
- Impact assessment: upstream callers (what breaks), downstream dependencies (what to retest)
- Risk level classification (HIGH/MEDIUM/LOW) based on blast radius
- Test scope recommendations with migration notes
- Integration with vlocity-dependency-indexer foundation skill
- Three comprehensive use cases: pre-change assessment, dependency chain analysis, refactoring scope
- Best practices guide and detailed limitations documentation
