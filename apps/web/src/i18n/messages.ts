export const locales = ["en", "pt-BR"] as const;

export type Locale = (typeof locales)[number];

export function hasLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}

export type Messages = {
  context: string;
  surfaces: Record<"toolbar" | "hero" | "form", string>;
  preview: string;
  previewHint: string;
  buttonSurface: (surface: string) => string;
  projectSettings: string;
  heroTagline: string;
  heroTitle: string;
  emailAddress: string;
  emailPlaceholder: string;
  selectedElement: string;
  selectButton: string;
  feedback: string;
  feedbackHint: string;
  noButton: string;
  reactions: string;
  reactionLabels: string[];
  critique: string;
  critiquePlaceholder: string;
  reviewInterpretation: string;
  reviewingInterpretation: string;
  describePreference: string;
  reviewDirectives: string;
  inspector: string;
  inspectorHint: string;
  reviewFeedback: string;
  reviewRegion: string;
  confirmInterpretation: string;
  reviewSelectionHint: string;
  keep: string;
  explore: string;
  generateAlternatives: string;
  generatingAlternatives: string;
  alternatives: string;
  alternativesRegion: string;
  changes: string;
  exploreRecipe: string;
  exploringRecipe: string;
  accept: string;
  almost: string;
  indifferent: string;
  rejectAll: string;
  preferenceMemory: (count: number) => string;
  emptyCritique: string;
  parsed: string;
  candidatesReady: string;
  wildCandidatesReady: string;
  accepted: (kind: string) => string;
  evidenceStored: (label: string, kind: string) => string;
  rejected: string;
};

export const messages: Record<Locale, Messages> = {
  en: {
    context: "Session context",
    surfaces: { toolbar: "toolbar", hero: "hero", form: "form" },
    preview: "Preview",
    previewHint: "Select the Button in this live UI to refine it.",
    buttonSurface: (surface) => `${surface} Button surface`,
    projectSettings: "Project settings",
    heroTagline: "Make each interaction intentional.",
    heroTitle: "Build a calmer workflow",
    emailAddress: "Email address",
    emailPlaceholder: "you@example.com",
    selectedElement: "Selected element",
    selectButton: "Select a Button before submitting feedback.",
    feedback: "Feedback",
    feedbackHint: "Feedback can change only visual appearance; its label, role, and state are not taste dimensions.",
    noButton: "Select the Button to refine it. This laboratory edits one component only.",
    reactions: "Absolute feedback",
    reactionLabels: ["like", "almost", "indifferent", "dislike"],
    critique: "Critique",
    critiquePlaceholder: "I like the recipe and spacing, but it is too rounded.",
    reviewInterpretation: "Review interpretation",
    reviewingInterpretation: "Reviewing interpretation…",
    describePreference: "Describe a visual preference before reviewing its interpretation.",
    reviewDirectives: "Review the visual directives. Nothing has been stored yet.",
    inspector: "Direct visual editor",
    inspectorHint: "Recipes derive background, border, hover, and focus tokens together.",
    reviewFeedback: "Review feedback",
    reviewRegion: "Review refinement interpretation",
    confirmInterpretation: "Confirm interpretation",
    reviewSelectionHint: "Checked attributes are kept. Unchecked attributes are explored.",
    keep: "Keep",
    explore: "Explore",
    generateAlternatives: "Generate constrained alternatives",
    generatingAlternatives: "Generating alternatives…",
    alternatives: "Constrained alternatives",
    alternativesRegion: "Constrained alternatives",
    changes: "Changes",
    exploreRecipe: "Explore recipe centroid",
    exploringRecipe: "Exploring recipe centroid…",
    accept: "Accept",
    almost: "Almost",
    indifferent: "Indifferent",
    rejectAll: "Reject all",
    preferenceMemory: (count) => `Preference memory: ${count} explicit action${count === 1 ? "" : "s"} stored locally when the API is running.`,
    emptyCritique: "Describe a visual preference before reviewing its interpretation.",
    parsed: "Review the visual directives. Nothing has been stored yet.",
    candidatesReady: "Constrained alternatives are ready.",
    wildCandidatesReady: "An opt-in recipe-centroid exploration was added.",
    accepted: (kind) => `${kind} was accepted.`,
    evidenceStored: (label, kind) => `${label} was stored for ${kind}; no winner was assumed.`,
    rejected: "None of these was recorded. No option was selected as a winner.",
  },
  "pt-BR": {
    context: "Contexto da sessão",
    surfaces: { toolbar: "barra de ferramentas", hero: "destaque", form: "formulário" },
    preview: "Pré-visualização",
    previewHint: "Selecione o botão nesta interface para refiná-lo.",
    buttonSurface: (surface) => `Área do botão: ${surface}`,
    projectSettings: "Configurações do projeto",
    heroTagline: "Faça cada interação ser intencional.",
    heroTitle: "Construa um fluxo de trabalho mais calmo",
    emailAddress: "Endereço de e-mail",
    emailPlaceholder: "voce@exemplo.com",
    selectedElement: "Elemento selecionado",
    selectButton: "Selecione um botão antes de enviar o feedback.",
    feedback: "Feedback",
    feedbackHint: "O feedback altera somente a aparência visual; rótulo, função e estado não são dimensões de gosto.",
    noButton: "Selecione o botão para refiná-lo. Este laboratório edita apenas um componente.",
    reactions: "Avaliação geral",
    reactionLabels: ["gosto", "quase", "indiferente", "não gosto"],
    critique: "Comentário",
    critiquePlaceholder: "Gosto da receita e do espaçamento, mas está arredondado demais.",
    reviewInterpretation: "Revisar interpretação",
    reviewingInterpretation: "Revisando interpretação…",
    describePreference: "Descreva uma preferência visual antes de revisar a interpretação.",
    reviewDirectives: "Revise as diretrizes visuais. Nada foi salvo ainda.",
    inspector: "Editor visual direto",
    inspectorHint: "As receitas definem em conjunto os tokens de fundo, borda, hover e foco.",
    reviewFeedback: "Revisar feedback",
    reviewRegion: "Revisar interpretação do refinamento",
    confirmInterpretation: "Confirmar interpretação",
    reviewSelectionHint: "Atributos marcados são mantidos. Atributos desmarcados são explorados.",
    keep: "Manter",
    explore: "Explorar",
    generateAlternatives: "Gerar alternativas restritas",
    generatingAlternatives: "Gerando alternativas…",
    alternatives: "Alternativas restritas",
    alternativesRegion: "Alternativas restritas",
    changes: "Alterações",
    exploreRecipe: "Explorar centroide da receita",
    exploringRecipe: "Explorando centroide da receita…",
    accept: "Aceitar",
    almost: "Quase",
    indifferent: "Indiferente",
    rejectAll: "Rejeitar todas",
    preferenceMemory: (count) => `Memória de preferências: ${count} ${count === 1 ? "ação explícita" : "ações explícitas"} salva${count === 1 ? "" : "s"} localmente quando a API está em execução.`,
    emptyCritique: "Descreva uma preferência visual antes de revisar a interpretação.",
    parsed: "Revise as diretrizes visuais. Nada foi salvo ainda.",
    candidatesReady: "As alternativas restritas estão prontas.",
    wildCandidatesReady: "Uma exploração opcional do centroide da receita foi adicionada.",
    accepted: (kind) => `${kind} foi aceito.`,
    evidenceStored: (label, kind) => `${label} foi salvo para ${kind}; nenhuma opção foi assumida como vencedora.`,
    rejected: "Nenhuma destas opções foi registrada. Nenhuma opção foi selecionada como vencedora.",
  },
};
