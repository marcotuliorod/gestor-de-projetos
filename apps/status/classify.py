from .models import ProjectState

# RODANDO nunca é atribuído aqui — só a execução de agentes (fase futura)
# grava esse estado diretamente, ligada a um TaskRun em andamento.


def classify_state(data: dict) -> tuple[str, str]:
    """Classifica o estado do projeto a partir do dict cru do coletor.

    Regra determinística e simples (RF-05 pede 4 estados úteis, não um motor
    de regras complexo):
      ci_status em failure/error -> PRECISA_DE_VOCE
      há PR aberto                -> EM_DIA
      caso contrário               -> PARADO
    """
    ci_status = data.get("ci_status", "")
    open_prs = data.get("open_prs", 0)

    if ci_status in ("failure", "error"):
        branch = data.get("branch", "")
        return ProjectState.PRECISA_DE_VOCE, f"CI falhando em {branch}."

    if open_prs > 0:
        ahead = data.get("ahead", 0)
        behind = data.get("behind", 0)
        return (
            ProjectState.EM_DIA,
            f"{open_prs} PR(s) aberto(s) — {ahead} commit(s) à frente da base, {behind} atrás.",
        )

    return ProjectState.PARADO, "Sem PRs abertos nem falhas de CI."
