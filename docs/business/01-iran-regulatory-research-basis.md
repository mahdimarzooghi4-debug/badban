# Iran Regulatory Research Basis — 2026-10-05

- **Status:** Research Baseline
- **Stage:** Business / Legal-Structure Validation
- **Purpose:** Evidence base for Decision 0014
- **Important:** This document is not legal advice. It records the current regulatory basis that must be re-verified before pilot and production.

## 1. Central Bank regulatory perimeter

### Source

**Law of the Central Bank of the Islamic Republic of Iran**, approved 1402/03/30.

Reference used:
https://nezamat.ir/post-44913/

### Relevant points

- The law defines banking operations and banking services.
- Article 37 provides that banking operations, banking services, foreign exchange, leasing-like supervised activity, payment-system activity, and creation/registration of supervised persons generally require Central Bank licensing within the applicable framework.
- Digital provision of banking operations/services does not remove the licensing requirement merely because the channel is web/mobile.

### Badban implication

Badban must not assume that a normal software/company entity can activate regulated lending or banking services without an applicable legal basis and authorization.

## 2. Qard-al-Hasan / credit providers

### Sources

**Seventh Development Plan of the Islamic Republic of Iran (1403–1407)**:
https://nezamat.ir/%D9%82%D8%A7%D9%86%D9%88%D9%86-%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D9%87-%D9%87%D9%81%D8%AA%D9%85-%D9%BE%DB%8C%D8%B4%D8%B1%D9%81%D8%AA-%D8%AC%D9%85%D9%87%D9%88%D8%B1%DB%8C-%D8%A7%D8%B3%D9%84%D8%A7%D9%85/

Legacy reference:
**Instruction on establishment, activity and supervision of Qard-al-Hasan funds**, approved 1388/05/20.

### Relevant points

- The Seventh Plan requires the Central Bank to regulate different types of credit institutions, including Qard-al-Hasan institutions, and to prepare/update the framework for Qard-al-Hasan funds.
- Qard-al-Hasan activity is not treated as an unregulated informal substitute for a lender.

### Badban implication

Every external Qard-al-Hasan provider must be onboarded as a real legal lender/provider with current authorization/status verified at onboarding time.

## 3. Non-governmental guarantee funds

### Sources

**Financing of Production and Infrastructure Act**, approved 1402:
https://nezamat.ir/%D9%82%D8%A7%D9%86%D9%88%D9%86-%D8%AA%D8%A3%D9%85%DB%8C%D9%86-%D9%85%D8%A7%D9%84%DB%8C-%D8%AA%D9%88%D9%84%DB%8C%D8%AF-%D9%88-%D8%B2%DB%8C%D8%B1%D8%B3%D8%A7%D8%AE%D8%AA%D9%87%D8%A7/

**Regulation on licensing establishment and activity of non-governmental guarantee funds**, approved 1403/05/28:
https://nezamat.ir/%D8%A2%DB%8C%DB%8C%D9%86%D9%86%D8%A7%D9%85%D9%87-%D8%B5%D8%AF%D9%88%D8%B1-%D9%85%D8%AC%D9%88%D8%B2-%D8%AA%D8%A3%D8%B3%DB%8C%D8%B3-%D9%88-%D9%81%D8%B9%D8%A7%D9%84%DB%8C%D8%AA-%D8%B5%D9%86/

**Regulation on guarantee activity-level rating of non-governmental guarantee funds**, approved 1404/05/08:
https://nezamat.ir/%D8%A2%DB%8C%DB%8C%D9%86-%D9%86%D8%A7%D9%85%D9%87-%D8%A7%D8%AC%D8%B1%D8%A7%DB%8C%DB%8C-%D8%AC%D8%B2%D8%A1-3%D9%802%D9%804-%D8%A8%D9%86%D8%AF-%D8%A8-%D9%85%D8%A7%D8%AF%D9%87-2-%D9%82%D8%A7%D9%86/

### Relevant points

- The law creates a framework for non-governmental guarantee funds.
- The 1403 regulation requires approval/license before activity.
- Guarantee funds may issue guarantees within the applicable framework.
- Banks and non-bank credit institutions may accept qualifying guarantees from these funds subject to the applicable rating/credit framework.
- Guarantee-fund activity is subject to supervisory ratios, capital requirements, registry/unique-identifier requirements, and collateral rules.
- The legal framework is primarily framed around financing and guarantee needs of production/service activities and contractual guarantees.

### Badban implication

A licensed guarantee fund is a strong candidate for the legal **Guarantee Issuer** role.

However, legal counsel/regulatory confirmation is mandatory before assuming the framework covers every Badban household or welfare credit product, especially consumer/livelihood loans not clearly tied to production/service activity.

## 4. Comprehensive Collateral System

### Source

**Financing of Production and Infrastructure Act**, especially Articles 7–9:
https://nezamat.ir/%D9%82%D8%A7%D9%86%D9%88%D9%86-%D8%AA%D8%A3%D9%85%DB%8C%D9%86-%D9%85%D8%A7%D9%84%DB%8C-%D8%AA%D9%88%D9%84%DB%8C%D8%AF-%D9%88-%D8%B2%DB%8C%D8%B1%D8%B3%D8%A7%D8%AE%D8%AA%D9%87%D8%A7/

### Relevant points

- The law recognizes a broad range of potentially pledgeable assets, including precious metals, securities, deposits and other financial/property rights subject to applicable rules.
- It establishes the Comprehensive Collateral System for collateral registration and lifecycle information.
- Where the legal system supports an asset class, internal Badban records are not a substitute for mandatory legal registration.

### Badban implication

Badban architecture must support external collateral identifiers and synchronization of registration, encumbrance, enforcement, and release.

## 5. Capital-market activities

### Sources

**Securities Market Act of the Islamic Republic of Iran**, approved 1384:
https://nezamat.ir/?p=30662

Related licensing rules for financial institutions under Securities and Exchange Organization supervision.

### Relevant points

- Investment funds and other defined capital-market financial institutions are regulated institutions.
- Establishment/operation of covered financial institutions and regulated securities-market activities are subject to the Securities and Exchange Organization framework.

### Badban implication

If Badban uses securities, fund units, or discretionary portfolio management, it should route regulated execution/management/custody functions through appropriately licensed/registered capital-market providers rather than assuming Badban Core may perform them directly.

## 6. Current architecture conclusion

Current evidence supports the following design principle:

```
One Badban Product Experience
≠
One Legal Entity Performing Every Regulated Function
```

Preferred model:

- Badban Core: product, policy, risk, workflow, integration, reporting.
- Guarantee Issuer: licensed guarantee vehicle / partner where legally applicable.
- Lender: bank, authorized Qard-al-Hasan provider, or other authorized lender.
- Asset Manager/Custodian: provider appropriate to the Asset Type.
- External collateral/legal registries: authoritative where required.
- Direct Lending: disabled until separately authorized.

## 7. Open legal questions before pilot

1. Does the pilot guarantee purpose fit the non-governmental guarantee-fund legal scope?
2. Can the selected bank/fund accept the proposed Badban guarantee instrument for the selected credit product?
3. Which entity may legally hold and enforce each selected Asset Type?
4. Which assets require Securities and Exchange Organization regulated providers?
5. Which pilot assets can/must use the Comprehensive Collateral System?
6. What exact AML/KYC split applies among Badban, lender, guarantor and custodian?
7. What consumer disclosure/consent obligations apply?
8. Can Badban itself ever perform direct lending under the intended structure, and under what authorization?
