# Decision 0014 — Regulated Operating Structure and Legal-Role Separation

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Legal Structure / Regulatory Architecture / Operating Model
- **Dependencies:** Decision 0003 — Asset Position Ownership by Funding Source; Decision 0005 — Hybrid Credit Delivery Model; Decision 0006 — External Lender Integration and Guarantee Lifecycle; Decision 0007 — Default, Claim, Recovery, and Loss Waterfall; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0010 — Risk Appetite and Guarantee Reserve Framework; Decision 0011 — Configurable Credit Product Rules; Decision 0013 — Participant Exit and Entitlement Rules

## Status of This Decision

This is a **business architecture proposal informed by current Iranian regulatory research**, not a final legal opinion.

Before production launch, every regulated role must be validated against then-current law, regulator interpretation, licensing status, product purpose, asset type, and counterparty contract.

No implementation may rely on the assumption that a generic Badban company is automatically permitted to lend, issue regulated guarantees, manage securities, hold regulated customer assets, or provide banking services.

## Regulatory Research Basis — 2026-10-05

The current legal framework supports several distinct regulated roles that are relevant to Badban:

1. The Law of the Central Bank of the Islamic Republic of Iran (1402) defines banking operations/services and provides that banking operations, banking services, payment-system activity, and establishment of supervised persons generally require Central Bank licensing.
2. The Securities Market Act treats investment funds and other capital-market financial institutions as regulated financial institutions; establishment/operation of covered financial institutions is subject to Securities and Exchange Organization licensing/registration.
3. The Financing of Production and Infrastructure Act (1402) and the 1403 regulation on non-governmental guarantee funds establish a licensed guarantee-fund framework. The regulation allows qualifying non-governmental guarantee funds to issue guarantees, and banks/credit institutions may accept those guarantees subject to the applicable credit/rating framework.
4. The same financing law recognizes a broad set of assets as potentially pledgeable and establishes the Comprehensive Collateral System for registration/management of collateral where applicable.
5. The Seventh Development Plan requires Central Bank regulation of credit institutions and Qard-al-Hasan funds and places those activities within the Central Bank regulatory perimeter.

These rules create a strong basis for **role separation**, but they do not by themselves prove that every Badban participant, loan purpose, guarantee type, or Asset Type fits every referenced license category.

## Decision

Badban shall be designed as **one product and one customer journey, but not necessarily one legal entity performing every regulated function**.

The preferred model is:

```
Badban Product / Orchestration Layer
        ↓
Asset & Entitlement Record
        ↓
Valuation / Risk / Guarantee Capacity Engine
        ↓
Licensed / Authorized Legal Roles
        ├─ Guarantee Issuer
        ├─ External Lender
        ├─ Asset Manager / Custodian
        ├─ Banking / Payment Rails
        └─ Other Regulated Provider, when required
```

The product architecture must preserve a single authoritative transaction model while recording the actual legal entity responsible for each regulated action.

## 1. Badban Core / Platform Entity

The Badban Core may act as the product, software, orchestration, policy, integration, reporting, and control layer.

Subject to final legal review, its core responsibilities may include:

- participant and program workflow;
- Asset Type Registry;
- Asset Position records;
- ownership/funding classification;
- valuation orchestration;
- guarantee-capacity calculation;
- policy/risk engine;
- lender/provider registry;
- workflow coordination;
- reconciliation;
- participant statements;
- governance/audit records;
- provider integrations;
- monitoring and reporting.

The Badban Core must not assume that software control or contractual orchestration gives it regulatory permission to perform a licensed financial function.

## 2. Guarantee Issuer Role

The legal entity that issues the enforceable Badban guarantee must be explicit.

### Preferred Regulatory Path

Where the product and guarantee purpose fall within the applicable legal scope, Badban should evaluate one of two models:

1. establish a properly licensed **non-governmental guarantee fund**; or
2. contract with an existing licensed guarantee fund that acts as the legal Guarantee Issuer.

Under the 1403 non-governmental guarantee-fund regulation:

- the guarantee fund is a separately regulated legal entity;
- commencement of activity requires regulatory approval/license;
- guarantee issuance and collateral rules are governed by the applicable framework;
- banks and non-bank credit institutions may accept qualifying fund guarantees subject to the regulatory credit/rating framework.

### Scope Warning

The current statutory guarantee-fund regime is strongly framed around financing and guarantee needs of production/service activities and contractual guarantees.

Badban must **not** assume without legal confirmation that all household, welfare, consumption, livelihood, or personal Qard-al-Hasan loans are eligible to use the same guarantee-fund route.

This is a mandatory legal-validation item before pilot product selection.

## 3. External Lender Role

For the preferred external-lender model, the lender of record remains the bank, Qard-al-Hasan institution/fund, or other legally authorized credit provider.

The external lender is responsible for the regulated lending functions assigned to it, including as applicable:

- borrower credit approval;
- legally valid credit contract;
- disbursement;
- repayment collection;
- lender-side accounting;
- regulatory reporting;
- delinquency servicing.

Decision 0009 remains binding:

```
External Loan Principal = Issued Badban Guarantee Amount
```

The lender's legal identity must always be preserved in the transaction record.

## 4. Badban Direct Lending

Direct lending remains an optional product capability but must be **regulator-gated**.

Badban must not activate direct lending merely because the software supports it.

Before activation, Badban must have one of:

- a legally authorized/licensed lending entity;
- an explicit statutory/legal basis permitting the contemplated credit activity;
- a structure formally confirmed by the competent regulator and legal counsel.

If the lending activity falls within the Central Bank regulatory perimeter, it must be carried out by an appropriately licensed/authorized entity.

Until that gate is passed:

```
Badban Direct Lending = DISABLED
```

in production policy.

## 5. Qard-al-Hasan Providers

Qard-al-Hasan products must be treated as provider-specific regulated credit products, not as an informal exception to the lender model.

The provider must have the legally required authorization/status for its activity.

Badban's integration must preserve:

- provider identity;
- product rules;
- approved limits;
- repayment rules;
- regulatory constraints;
- guarantee acceptance rules.

Badban must re-check the then-current Central Bank rules before onboarding each Qard-al-Hasan provider.

## 6. Securities and Capital-Market Assets

If an Asset Type is a security, investment-fund unit, or another capital-market instrument, Badban must not assume it can directly provide regulated portfolio-management, brokerage, fund-management, or custody services.

Where the activity falls within capital-market regulation, Badban should use appropriately licensed/registered providers such as the applicable:

- fund;
- portfolio manager;
- broker;
- investment manager;
- depository/custody infrastructure;
- other Securities and Exchange Organization supervised institution.

Badban may orchestrate the product experience while the regulated provider performs the regulated activity.

## 7. Non-Securities Assets

For physical gold, cash-like assets, deposits, receivables, intellectual property, or other approved assets, the lawful custody/control model must be determined **per Asset Type**.

There is no assumption that one custodian/license is valid for every asset class.

Each Asset Type policy must therefore identify:

- legal owner;
- legal holder/custodian;
- permitted pledge/encumbrance method;
- valuation authority;
- enforcement path;
- release path;
- applicable registry/system;
- regulator/authority, if any.

## 8. Comprehensive Collateral System

Where an asset and transaction are eligible for registration in the Comprehensive Collateral System under applicable law and the system is operational for that asset class, Badban should use the legally required/approved registration and lifecycle process.

Badban's internal collateral ledger does not replace a mandatory external legal registry.

The system architecture must support storing:

- external collateral identifier;
- registration status;
- encumbrance status;
- valuation reference;
- enforcement status;
- release status;
- synchronization timestamp.

## 9. Customer Money and Settlement

Badban must not treat participant/customer money as ordinary corporate cash.

Where participant funds, loan disbursements, repayments, reserve cash, or settlement money must be held in regulated banking/payment accounts, the funds should flow through appropriately authorized banking/payment infrastructure.

The product ledger must distinguish:

- Badban corporate funds;
- program funds;
- participant-owned funds;
- guarantee reserve;
- lender funds;
- settlement/recovery funds.

Commingling is prohibited unless explicitly lawful and accounted for.

## 10. Legal Entity Role Registry

Badban shall maintain a **Legal Entity Role Registry**.

For every active provider/entity, the system must record:

- legal entity name;
- national/company identifier;
- role(s);
- regulator/competent authority;
- license/authorization type;
- license identifier;
- effective date;
- expiry/renewal date where applicable;
- permitted product scope;
- permitted Asset Types;
- status: ACTIVE / SUSPENDED / EXPIRED / TERMINATED;
- evidence/reference;
- last compliance review date.

A provider cannot perform a regulated role in Badban when its required authorization is not valid.

## 11. Capability Matrix

Badban must maintain a policy-controlled matrix such as:

```
Legal Entity
× Regulated Role
× Product
× Asset Type
× Jurisdiction
× Authorization
= ALLOWED / NOT ALLOWED / REQUIRES REVIEW
```

The system must not infer permission merely from the entity being an existing Badban partner.

## 12. One Brand, Multiple Legal Counterparties

Badban may present one unified user interface and brand.

However, contracts and disclosures must clearly identify the actual legal counterparty for each function, including:

- asset ownership/custody;
- guarantee issuance;
- lending;
- repayment collection;
- investment management;
- claim settlement.

A unified user experience must not create a false statement that Badban Core is the legal lender, custodian, or guarantor when another entity performs that role.

## 13. Guarantee Contract Boundary

Badban must distinguish:

- a platform-calculated **Guarantee Capacity**;
- an approved **Guarantee Reservation**;
- a legally issued **Guarantee Instrument**.

Only the authorized Guarantee Issuer may create the legal guarantee instrument.

The Badban engine may calculate and approve capacity under policy, but the legal guarantee becomes active only after issuance by the authorized legal entity and synchronization back to Badban.

## 14. Asset Management Boundary

Badban's policy engine may decide which Asset Types are eligible and may calculate risk treatment.

It must not silently cross into regulated discretionary asset management.

Where a licensed manager is required:

```
Badban Policy
      ↓
Approved Mandate
      ↓
Licensed Asset Manager / Provider
      ↓
Execution / Custody
      ↓
Authoritative Confirmation back to Badban
```

## 15. Compliance Gate Before Provider Activation

Before an entity becomes ACTIVE in the relevant registry, Badban must have:

- verified legal identity;
- verified authorization/license where required;
- approved contract;
- defined role boundary;
- defined data/reporting obligations;
- defined complaint/dispute path;
- defined AML/KYC responsibility;
- defined operational and security controls;
- defined exit/termination process.

## 16. Legal Change Management

Regulatory conclusions are time-sensitive.

Badban must maintain a legal/regulatory review process for:

- new Asset Types;
- new lender types;
- new guarantee structures;
- direct lending;
- new investment products;
- new custody models;
- material policy changes.

A material regulatory change may suspend new transactions without invalidating existing contracts unless the law requires otherwise.

## 17. Mandatory Open Legal Questions

Before production pilot approval, legal counsel/regulatory engagement must answer at least:

1. Does the intended Badban guarantee for the selected pilot loan purpose fall within the non-governmental guarantee-fund regime?
2. Can the selected bank/Qard-al-Hasan lender accept that specific guarantee instrument for the selected borrower/product?
3. Which entity is legally entitled to take and enforce the selected collateral?
4. Which Asset Types require a capital-market licensed manager/custodian?
5. Which Asset Types can/must be registered in the Comprehensive Collateral System?
6. What consumer/participant disclosures and consent are required?
7. Which AML/KYC obligations belong to Badban Core versus lender/guarantor/custodian?
8. Is any contemplated direct-lending activity legally permissible without a credit-institution license? If yes, under what exact basis?
9. What accounting/legal segregation is required for participant-owned, program-owned, reserve, and settlement funds?
10. What legal process applies to claim enforcement, death, incapacity, succession, and participant exit?

## 18. Non-Negotiable Controls

1. No regulated function is activated without a verified legal basis.
2. One user journey does not imply one legal entity.
3. The legal lender, guarantor, custodian, and asset manager must be explicit.
4. Badban Core cannot self-declare a regulated license.
5. Direct lending remains disabled until its legal gate is passed.
6. Securities-market activities use appropriately regulated providers where required.
7. External legal collateral registration overrides an internal-only record where law requires external registration.
8. License/authorization expiry or suspension blocks new regulated transactions.
9. Participant/customer money is segregated according to its legal/economic ownership.
10. Every regulated action must be attributable to the legal entity that actually performed it.

## Recommended Initial Operating Structure

Subject to legal validation, the preferred pilot structure is:

```
Badban Core / Platform
        │
        ├─ Guarantee Issuer:
        │    Licensed guarantee vehicle / approved partner
        │
        ├─ Lender:
        │    Bank or authorized Qard-al-Hasan provider
        │
        ├─ Asset / Collateral Provider:
        │    Authorized custodian / bank / capital-market provider
        │
        └─ Registries:
             Required external collateral / regulatory systems
```

This structure preserves the integrated Badban experience while avoiding the assumption that a single unlicensed company can legally perform every financial function.

## Consequences

1. Badban becomes a regulated-finance orchestration platform rather than a monolithic legal entity.
2. The preferred external-lender architecture remains intact.
3. A licensed guarantee-fund route becomes a serious candidate for the formal Guarantee Issuer role, subject to scope confirmation.
4. Direct lending remains technically supported but legally gated.
5. Asset-specific custody and investment licensing are handled by provider capability rather than hard-coded assumptions.
6. The technical architecture will need explicit provider-role, license, legal-counterparty, and external-registry models.

## Follow-up

If Accepted, the next Business decision should define the **Accounting and Sub-Ledger Model**, including:

- participant-owned assets;
- program-attributed assets;
- guarantee reserve;
- encumbrances;
- lender obligations;
- claim settlement;
- recoveries;
- return allocation;
- future-financial balances;
- direct-lending receivables, if enabled.

After that, Badban should define the pilot boundary and validate all selected legal roles before Technical implementation.
