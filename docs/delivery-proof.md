# Delivery verification — proof of function

SamePage records what two participants agreed would count as completed work. Only the person responsible for delivery submits a result; only the other participant can accept or dispute each item.

## The lifecycle demonstrated

1. The initiator and recipient approve the agreement.
2. One party proposes a checklist, specifying each deliverable and objective acceptance criteria.
3. The other party approves the checklist or requests a revised version. The author cannot approve their own checklist.
4. The responsible party submits an evidence statement and reference for a deliverable.
5. The reviewer compares it with the acceptance criteria and either accepts or gives a correction request.
6. Disputed work can be resubmitted. Previous statements and review notes remain in the audit log.
7. The agreement is complete only after every checklist item has been accepted.

## One-command deterministic proof

From the project root:

```powershell
uv run --python 3.13 --with-requirements requirements.txt python -m scripts.prove_delivery
```

The script creates synthetic participants and an isolated temporary database, runs an end-to-end two-person delivery scenario, and asserts that completion cannot occur before every item has been accepted. It does not call Meta's API or modify your actual agreements.

To run the full automated suite:

```powershell
uv run --python 3.13 --with-requirements requirements.txt python -m pytest -q
```

## Live interface demonstration

Create a **new** accepted agreement with two different browser sessions. Under **Delivery**, propose two measurable deliverables. The other participant approves the list. Submit one item, request a correction, resubmit it, and then accept it. Submit and accept the second item. Open **View agreement** to see the item-by-item delivery record, including the review outcome.

These checks demonstrate software state transitions and an auditable history, **not independent proof that physical work is complete**. The reviewing participant is responsible for inspecting the work. Audit hashes are local consistency checks, not legal attestations. This is a local prototype and should not be deployed for real customer data without proper authentication, encryption, abuse protection and a hosted database.

The Meta conversation-analysis path is separate and can propose changes to agreement terms, but cannot approve the checklist or override a human's acceptance decision. The checklist proof does not claim measured Meta model accuracy.
