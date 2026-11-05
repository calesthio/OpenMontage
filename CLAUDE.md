# OpenMontage

**MANDATORY: Read [`AGENT_GUIDE.md`](AGENT_GUIDE.md) before responding to ANY user message.**

Do not act on the user's request until you have read AGENT_GUIDE.md.
It contains routing rules that determine your first action based on what the user asked.
Skipping it WILL cause you to take the wrong action.

Production instructions are in AGENT_GUIDE.md; the repository rules below also apply.

## Reglas transversales

- Al terminar y superar las pruebas pertinentes, haz commit local sin pedir permiso, solo de los archivos de la tarea. Push solo con autorización explícita.
- Puede haber varias sesiones de agentes trabajando a la vez en este repo: comprueba `git status` y que el HEAD es tuyo antes de stagear, commitear o reescribir historia.
- Aplica siempre KISS: la solución más pequeña y simple que resuelva el caso actual.

## Secretos

Leer o ver un secreto en una sesión no obliga a rotarlo. Se rotan cada 90 días para minimizar riesgos, salvo que se expongan en un sitio público o a terceros o queden invalidados: entonces, en el momento.
