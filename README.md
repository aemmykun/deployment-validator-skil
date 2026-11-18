# Deployment_Validation_Skill

To make the framework deterministic and machine-enforceable, I would define **profiles** as _control applicability models_ and **rules** as _individual control definitions_.

The relationship becomes:

```text
validation.profile.json
        |
        v
Selects required control groups
        |
        v
validation.rules.json
        |
        v
Individual controls evaluated
        |
        v
validation.schema.json
        |
        v
Validation result
```

---

# validation.profile.json Format

Purpose:

- Define deployment types
- Define required control families
- Define decision policies
- Avoid hardcoding assumptions into the validator

## Schema

```json
{
  "version": "1.0",

  "profiles": {
    "<profile-name>": {

      "description": "",

      "requires": [],

      "optional": [],

      "decision_policy": {
        "unverified_required_blocks": true,
        "fail_required_blocks": true
      }
    }
  }
}
```

---

## Example

```json
{
  "version": "1.0",

  "profiles": {

    "minimal": {

      "description": "Single-process application",

      "requires": [
        "runtime"
      ],

      "optional": [
        "observability"
      ],

      "decision_policy": {
        "unverified_required_blocks": true,
        "fail_required_blocks": true
      }
    },

    "platform": {

      "description": "Production platform",

      "requires": [
        "runtime",
        "database",
        "observability"
      ],

      "optional": [],

      "decision_policy": {
        "unverified_required_blocks": true,
        "fail_required_blocks": true
      }
    },

    "governed-platform": {

      "description": "Governance-first platform",

      "requires": [
        "runtime",
        "database",
        "observability",
        "security",
        "governance",
        "auditability"
      ],

      "optional": [],

      "decision_policy": {
        "unverified_required_blocks": true,
        "fail_required_blocks": true
      }
    }
  }
}
```

---

# validation.rules.json Format

Purpose:

Defines every control individually.

---

## Schema

```json
{
  "version": "1.0",

  "control_groups": {},

  "controls": []
}
```

---

## Control Groups

```json
{
  "control_groups": {

    "runtime": {
      "description": "Runtime deployment validation"
    },

    "database": {
      "description": "Database readiness validation"
    },

    "observability": {
      "description": "Monitoring and alerting"
    },

    "security": {
      "description": "Authentication and authorization"
    },

    "governance": {
      "description": "Governance controls"
    },

    "auditability": {
      "description": "Audit requirements"
    }
  }
}
```

---

## Control Definition

```json
{
  "id": "",
  "name": "",
  "group": "",
  "required_evidence": [],
  "evaluation": {},
  "blocking": true
}
```

---

# Example Runtime Controls

```json
{
  "controls": [

    {
      "id": "RUN-001",

      "name": "Docker daemon validation",

      "group": "runtime",

      "blocking": true,

      "required_evidence": [
        "docker_runtime"
      ],

      "evaluation": {
        "type": "presence"
      }
    },

    {
      "id": "RUN-002",

      "name": "Compose syntax validation",

      "group": "runtime",

      "blocking": true,

      "required_evidence": [
        "compose_file"
      ],

      "evaluation": {
        "type": "syntax"
      }
    }
  ]
}
```

---

# Example Observability Controls

```json
{
  "id": "OBS-001",

  "name": "Prometheus monitoring",

  "group": "observability",

  "blocking": true,

  "required_evidence": [
    "prometheus_config"
  ],

  "evaluation": {
    "type": "configuration"
  }
}
```

---

# Governance Controls

Notice these require explicit evidence.

```json
{
  "id": "GOV-001",

  "name": "Fail-closed enforcement",

  "group": "governance",

  "blocking": true,

  "required_evidence": [
    "deny_by_default_policy",
    "failure_path"
  ],

  "evaluation": {
    "type": "governance"
  }
}
```

---

# Example Auditability Controls

```json
{
  "id": "AUD-001",

  "name": "Immutable audit trail",

  "group": "auditability",

  "blocking": true,

  "required_evidence": [
    "audit_storage",
    "write_protection"
  ],

  "evaluation": {
    "type": "audit"
  }
}
```

---

# Control Outcome Model

Every control must resolve to exactly one state:

```json
{
  "PASS": {
    "meaning": "Evidence demonstrates compliance"
  },

  "FAIL": {
    "meaning": "Evidence demonstrates non-compliance"
  },

  "UNVERIFIED": {
    "meaning": "Required evidence missing"
  },

  "NOT_APPLICABLE": {
    "meaning": "Control not required by profile"
  }
}
```

---

# Decision Algorithm

The validator should use:

```json
{
  "decision_engine": {

    "required_fail": "NOT_READY",

    "required_unverified": "NOT_READY",

    "blocking_fail": "NOT_READY",

    "all_required_pass": "READY",

    "all_required_pass_with_nonblocking_findings":
      "READY_WITH_WARNINGS"
  }
}
```

---

# TenantSage Governed Platform Example

```json
{
  "profile": "governed-platform",

  "required_groups": [
    "runtime",
    "database",
    "observability",
    "security",
    "governance",
    "auditability"
  ]
}
```

This means controls for:

```text
RUN-*
DB-*
OBS-*
SEC-*
GOV-*
AUD-*
```

are automatically in scope.

## The validator never assumes Prometheus, Grafana, governance controls, or databases exist. Instead, the selected profile determines which control groups become mandatory, and the rules file defines how each control is evaluated. This keeps the framework reusable for TenantSage, Firestore governance reviews, FastAPI deployments, SQL migrations, and infrastructure validation without changing validator code.