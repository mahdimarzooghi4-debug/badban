# Sprint 69 — Figma Institution Person Financial Case

**Status:** Backend-integrated read-only visual candidate, stacked on Draft PR #79; unmerged.
**Figma:** Badban `ubJTK7Vt3lwSEeVdjyn59n`, Institution / 04 `244:283` (1440×900).
**Backend owner:** Existing institution-scoped `GET /api/v1/support-institution/programs/{program_id}/beneficiaries/{participant_id}/episodes/{episode_id}/financial-case` and supporting Program/Beneficiary list pagination.

## Work done

- Reuse the already-integrated `InstitutionFinancialDetail`, `verifiedInstitutionCase`, `InstitutionPeople` and program/beneficiary selection instead of creating a parallel dashboard/backend endpoint.
- Pass the actual selected authorized program name and beneficiary record to the case screen; bind the visual identity card to authenticated program and real participant/episode identifiers. No mock person name, national ID, fake beneficiary role or fake organization is used.
- Add Figma-matched two-column identity and organizational-asset cards, read-only financial information rows, rights notice, responsive RTL layout, and two original Figma person/lock SVG assets exported from nodes `244:327` and `244:354` as versioned local assets.
- Show only the **recorded** organizational asset count in this bounded response and separate it from personally owned assets. Asset quantities are not assumed to be currency or fungible capital. Data are not summed across ownership, currency, episode or program.
- The backend case does **not** provide a canonical organizational-capital amount, personal withdrawal entitlement, funding request ledger or settlement/payment status. These fields therefore display clearly as unavailable, never as numeric zero, "PAID", completed financing, or Figma's 150-million-rial example.
- Keep the existing case-level assets, valuation observations, guarantees, loan mirror, pension and post-exit support details below the Figma overview. The valuation rows remain observations with source and freshness, never a selected/guaranteed price.
- Defense in depth: the new read-only view rejects program, participant or participation-episode mismatches even if called outside its validated parent loader.

## Tests, limitations, gates

Vitest server-rendered UI tests cover verified-scope binding, ownership separation, missing financial amounts, forbidden demo values and exact Figma icon references. Python repository tests confirm SVG geometry and static callsites.

The Figma `246:332` "organization financial history" and `246:512` "organization reporting" frames contain sample financial transactions and aggregate capital values; **they are not enabled** from this case-scoped API. A finance ledger/report contract is required from the authorized backend before these screens can be claimed live.

Full exact-head CI and COMMENTED technical Code Review are required. Real IdP-backed browser E2E, pixel parity, Stage, QA, release approval and Production deployment remain separate gates. Do not merge/deploy or activate real payments or grant individual ownership of organizational principal without explicit authorization.
