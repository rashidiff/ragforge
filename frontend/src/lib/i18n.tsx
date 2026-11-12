import { createContext, useCallback, useContext } from "react";
import type { ReactNode } from "react";

export type Locale = "en" | "fr";
const messages: Record<Exclude<Locale, "en">, Record<string, string>> = {
  fr: Object.assign(
    {
      "Chat navigation": "Navigation des conversations",
      "Main navigation": "Navigation principale",
      "Skip to content": "Aller au contenu",
      "Close navigation": "Fermer la navigation",
      "Open navigation": "Ouvrir la navigation",
      "Your workspace": "Votre espace",
      "Local workspace": "Espace local",
      "Connecting…": "Connexion…",
      "Use light theme": "Thème clair",
      "Use dark theme": "Thème sombre",
      "LLM model": "Modèle LLM",
      "Choose a model": "Choisir un modèle",
      "Loading models…": "Chargement des modèles…",
      "Other model…": "Autre modèle…",
      "Custom model ID": "Identifiant du modèle",
      "Use model": "Utiliser ce modèle",
      "Reload models": "Recharger les modèles",
      "Model documentation": "Documentation des modèles",
      "Choose your model from the menu at the top of the chat.": "Choisissez votre modèle dans le menu en haut de la conversation.",
      "Model access depends on your provider account.": "Accès aux modèles selon votre compte fournisseur.",
      "Interface language": "Langue de l’interface",
      "New chat": "Nouvelle conversation",
      "Creating…": "Création…",
      Library: "Bibliothèque",
      Settings: "Paramètres",
      Conversations: "Conversations",
      "Loading chats…": "Chargement des conversations…",
      "Your conversations will appear here.":
        "Vos conversations apparaîtront ici.",
      Save: "Enregistrer",
      Cancel: "Annuler",
      Rename: "Renommer",
      Delete: "Supprimer",
      "Chat title": "Titre de la conversation",
    },
    {
      "Close error": "Fermer l’erreur",
      "Make room for a clearer answer.":
        "Faites place à une réponse plus claire.",
      "Create a conversation, collect your PDFs, and keep the original context close at hand.":
        "Créez une conversation, rassemblez vos PDF et gardez le contexte à portée de main.",
      "Conversation memory could not be updated":
        "La mémoire de conversation n’a pas pu être mise à jour",
      "Your saved messages remain available.":
        "Vos messages enregistrés restent disponibles.",
      "Could not copy the answer. Select its text to copy it manually.":
        "Impossible de copier la réponse. Sélectionnez son texte pour la copier.",
      "Interrupted answer · incomplete": "Réponse interrompue · incomplète",
      "Ask about your PDFs…": "Posez une question sur vos PDF…",
      Stop: "Arrêter",
      Send: "Envoyer",
      "Compacting previous conversation messages":
        "Réduction du contexte précédent",
      "Original PDFs and conversation history stay on this computer. Remote providers may receive selected excerpts and conversation context when generation is enabled.":
        "Les PDF originaux et l’historique restent sur cet ordinateur. Les fournisseurs distants peuvent recevoir des extraits et le contexte nécessaires à la génération.",
      "Your documents, together.": "Vos documents, réunis.",
      "PDFs are shared across chats once local indexing succeeds.":
        "Les PDF sont accessibles dans les conversations après l’indexation locale.",
      "Rebuild index": "Reconstruire l’index",
      "Upload PDF": "Importer un PDF",
      "Uploading and validating PDF…": "Import et validation du PDF…",
      "Drop a PDF here, or choose Upload PDF.":
        "Déposez un PDF ici ou choisissez Importer un PDF.",
      "Original files and all indexing stay on this computer.":
        "Les fichiers originaux et l’indexation restent sur cet ordinateur.",
      "Loading Library…": "Chargement de la bibliothèque…",
      "Library documents": "Documents de la bibliothèque",
      Preview: "Aperçu",
      Reindex: "Réindexer",
      Remove: "Retirer",
      Page: "Page",
      "Open PDF": "Ouvrir le PDF",
      "Close PDF preview": "Fermer l’aperçu PDF",
      "Settings & privacy": "Paramètres et confidentialité",
      "The connection test checks the OpenAI Responses protocol at this URL. Tool and usage capabilities are explicit endpoint settings; unsupported behavior remains an error or is reported unavailable.":
        "Le test vérifie le protocole OpenAI Responses à cette adresse. Les capacités d’outils et d’usage sont configurées explicitement ; les fonctions non prises en charge restent signalées.",
      "Keys stay in session memory by default. The browser field clears after saving. A missing OS vault produces an error and never falls back to a file.":
        "Les clés restent en mémoire de session par défaut. Le champ du navigateur est vidé après l’enregistrement. Si le coffre système manque, une erreur est affichée sans enregistrer la clé dans un fichier.",
      "Key status": "État de la clé",
      configured: "configurée",
      "not configured for this provider": "non configurée pour ce fournisseur",
      "The key is never returned by the API.":
        "La clé n’est jamais renvoyée par l’API.",
      "Local document processing": "Traitement local des documents",
      "Embedding model": "Modèle d’embeddings",
      "Embedding revision": "Révision du modèle",
      "Changing the embedding model requires a full local Library rebuild. Initial model and package downloads may need internet access.":
        "Changer le modèle d’embeddings nécessite de reconstruire toute la bibliothèque locale. Le téléchargement initial du modèle et des paquets peut nécessiter Internet.",
      "OCR runs locally with Tesseract. Missing Tesseract or language packs produces a warning, and scans that remain unreadable are not marked searchable.":
        "L’OCR s’exécute localement avec Tesseract. L’absence de Tesseract ou de langues affiche un avertissement ; les pages illisibles ne sont pas indexées.",
      "OCR languages": "Langues OCR",
      "Model context tokens": "Jetons de contexte du modèle",
      "Maximum output tokens": "Jetons de sortie maximum",
      "Local data and remote generation":
        "Données locales et génération distante",
      "Loading settings…": "Chargement des paramètres…",
      "A key is configured": "Une clé est configurée",
      "Enter a provider key": "Saisissez une clé fournisseur",
      "Saving…": "Enregistrement…",
      "Testing…": "Test en cours…",
      "Your workspace stays local.": "Votre espace reste local.",
      "PDFs and indexes stay on this computer. A selected remote provider receives only retrieved PDF snippets, your question, instructions and needed conversation context.":
        "Les PDF et les index restent sur cet ordinateur. Le fournisseur distant choisi reçoit uniquement les extraits récupérés, votre question, les instructions et le contexte nécessaire.",
      "Save key in the OS credential vault":
        "Enregistrer la clé dans le coffre-fort du système",
      "Remove this PDF from the Library? Historical chats will be preserved.":
        "Retirer ce PDF de la bibliothèque ? Les conversations historiques seront conservées.",
      "from the Library? Historical chats will be preserved.":
        "de la bibliothèque ? Les conversations historiques seront conservées.",
      "PDF Library": "Bibliothèque PDF",
      Queued: "En attente",
      "Loading local embedding model": "Chargement du modèle local",
      "Extracting pages": "Extraction des pages",
      "Checking or running local OCR":
        "Vérification ou exécution de l’OCR local",
      "Chunking text": "Découpage du texte",
      "Embedding locally": "Vectorisation locale",
      "Publishing index": "Publication de l’index",
      Ready: "Prêt",
      Failed: "Échec",
      "Removing PDF": "Suppression du PDF",
      "Delete this chat?": "Supprimer cette conversation ?",
      "Delete chat": "Supprimer la conversation",
      "Deleting…": "Suppression…",
      "Local storage · No account": "Stockage local · Sans compte",
      Conversation: "Conversation",
      "Loading conversation…": "Chargement de la conversation…",
      You: "Vous",
      Assistant: "Assistant",
      "Copy answer": "Copier la réponse",
      Copied: "Copié",
      "Dismiss generation error": "Fermer l’erreur de génération",
      "Dismiss copy error": "Fermer l’erreur de copie",
      "Retry last response": "Réessayer la dernière réponse",
      "Retry memory update": "Réessayer la mise à jour de mémoire",
      Message: "Message",
      "A workspace for your PDFs": "Un espace pour vos PDF",
      "Start with your documents.": "Commencez avec vos documents.",
      "Open Library": "Ouvrir la bibliothèque",
      "Choose PDF file": "Choisir un fichier PDF",
      "Language model": "Modèle de langage",
      Provider: "Fournisseur",
      "Model name": "Nom du modèle",
      "API key": "Clé API",
      "Save settings": "Enregistrer les paramètres",
      "Test connection": "Tester la connexion",
      "Remove key": "Supprimer la clé",
      "Enable optional local OCR": "Activer l’OCR local facultatif",
      "Ask questions grounded in your active PDF Library.":
        "Posez des questions fondées sur vos PDF actifs.",
      "Your documents, in focus": "Vos documents, en évidence",
      "Preparing request…": "Préparation de la demande…",
      "Settings could not be loaded.": "Impossible de charger les paramètres.",
      "Settings could not be saved.":
        "Impossible d’enregistrer les paramètres.",
      "Settings saved. The API key was cleared from this form.":
        "Paramètres enregistrés. La clé API a été effacée du formulaire.",
      "The provider key was removed.": "La clé du fournisseur a été supprimée.",
      "The key could not be removed.": "Impossible de supprimer la clé.",
      "The connection test failed.": "Le test de connexion a échoué.",
      "Dismiss Library error": "Fermer l’erreur de la bibliothèque",
      "Upload one PDF at a time so each indexing job can finish.":
        "Importez un PDF à la fois pour permettre à chaque indexation de se terminer.",
      "Only PDF files are accepted.": "Seuls les fichiers PDF sont acceptés.",
      "Upload failed.": "Échec de l’importation.",
      "Library could not be loaded.": "Impossible de charger la bibliothèque.",
      "Library update failed.": "Échec de la mise à jour de la bibliothèque.",
      pages: "pages",
      "PDF source": "Source PDF",
      "Close source": "Fermer la source",
      "Loading source…": "Chargement de la source…",
      "This source is unavailable.": "Cette source n’est pas disponible.",
      "Open PDF at page": "Ouvrir le PDF à la page",
      "The request could not finish. Please retry.":
        "La demande n’a pas abouti. Veuillez réessayer.",
      "and its conversation memory will be removed. Local backups may still contain it. Other chats and your PDF Library are preserved.":
        "et sa mémoire de conversation seront supprimées. Les sauvegardes locales peuvent encore les contenir. Les autres conversations et la bibliothèque PDF seront conservées.",
      "Endpoint supports the configured Library tools":
        "Le point de terminaison prend en charge les outils de bibliothèque configurés",
      "Endpoint reports token usage":
        "Le point de terminaison rapporte l’utilisation des jetons",
      "Responses API base URL": "URL de base de l’API Responses",
      "There is no account, analytics, or telemetry. Provider calls and initial model/package downloads require internet access.":
        "Aucun compte, aucune analyse ni télémétrie. Les appels au fournisseur et les téléchargements initiaux de modèles et de paquets nécessitent Internet.",
      "Conversation history, activity logs, PDFs, indexes and memory are stored locally. Local history can contain sensitive text; files are not encrypted by the application.":
        "L’historique, les journaux, les PDF, les index et la mémoire sont stockés localement. L’historique peut contenir des données sensibles ; l’application ne chiffre pas les fichiers.",
      "Export as Markdown": "Exporter en Markdown",
      "Export as JSON": "Exporter en JSON",
      "Export warning":
        "L’export contient l’historique verbatim et peut inclure du texte sensible. Continuer ?",
      "Backup warning":
        "La sauvegarde contient l’historique verbatim et peut inclure du texte sensible. Continuer ?",
      "Download raw history backup":
        "Télécharger la sauvegarde brute de l’historique",
      "This message looks like it may contain an API key or secret. It will be saved verbatim in local history and may be sent to the selected provider. Remove it before sending if unintended.":
        "Ce message semble contenir une clé API ou un secret. Il sera enregistré tel quel dans l’historique local et peut être envoyé au fournisseur choisi. Supprimez-le avant l’envoi si cela n’est pas intentionnel.",
      "Connected to": "Connecté à",
      using: "avec",
      "using OpenAI Responses.": "avec OpenAI Responses.",
      "Library tools": "Outils de bibliothèque",
      "token usage": "utilisation des jetons",
      available: "disponibles",
      unavailable: "indisponibles",
      reported: "rapportée",
      upload: "importation",
      reindex: "réindexation",
      rebuild: "reconstruction",
      delete: "suppression",
    },
  ),

};

interface LocaleContextValue {
  locale: Locale;
  t: (english: string) => string;
}
const LocaleContext = createContext<LocaleContextValue>({
  locale: "en",
  t: (value) => value,
});

export function translate(locale: Locale, english: string) {
  const defaults: Record<string, string> = {
    "Export warning":
      "This export contains verbatim conversation history and may include sensitive text. Continue?",
    "Backup warning":
      "This backup contains verbatim conversation history and may include sensitive text. Continue?",
  };
  return locale === "en"
    ? (defaults[english] ?? english)
    : (messages[locale][english] ?? defaults[english] ?? english);
}

export function LocaleProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  const t = useCallback(
    (english: string) => translate(locale, english),
    [locale],
  );
  return (
    <LocaleContext.Provider value={{ locale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}
