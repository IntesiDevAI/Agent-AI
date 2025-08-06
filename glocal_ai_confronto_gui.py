#!/usr/bin/env python3
"""
glocal_ai_confronto_gui.py
==========================

Interfaccia grafica (GUI) per eseguire il confronto tra l’estrazione
dei dati da un PDF tramite Google Document AI e/o ChatGPT/LLM senza
dover utilizzare la riga di comando.  La GUI permette di:

* selezionare un file PDF tramite una finestra di dialogo;
* scegliere il metodo di estrazione (Google Document AI, ChatGPT, o
  entrambi);
* avviare l’estrazione e visualizzare il risultato JSON in una
  finestra di testo scrollabile;
* facoltativamente salvare il risultato in un file ``.json``.

Per funzionare, la parte relativa a Document AI richiede le stesse
variabili d’ambiente di ``glocal_ai_confronto.py`` (vedi file
``glocal_ai_confronto.py``).  La parte relativa a ChatGPT richiede
una chiave API valida per il provider scelto.

"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import requests
from typing import Any

# Carichiamo automaticamente variabili da file .env, se presente.  Questo permette
# di impostare chiavi e configurazioni senza definire manualmente le
# variabili d'ambiente prima dell'avvio.  Se la libreria python-dotenv non
# è disponibile, l'import genera un'eccezione che ignoriamo.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Importiamo le funzioni di estrazione dal modulo CLI
try:
    from glocal_ai_confronto import (
        extract_with_google_document_ai,
        extract_with_chatgpt,
    )
except ImportError as e:
    raise ImportError(
        "Impossibile importare le funzioni dal modulo glocal_ai_confronto. "
        "Assicurati che glocal_ai_confronto.py sia nella stessa directory e "
        "contenga le funzioni di estrazione."
    ) from e


# ----------------------------------------------------------------------------
#   AutocompleteCombobox
#
# Questa classe estende ttk.Combobox per implementare un comportamento di
# autocompletamento semplice.  L'utente può digitare parte del nome del
# modello e la lista a discesa mostrerà solo le opzioni che contengono
# quella stringa (case-insensitive).  Inoltre, se viene impostata una
# lista di completamento tramite set_completion_list(), la combobox
# aggiorna automaticamente i propri valori.  Questo widget viene
# utilizzato per selezionare il modello LLM.
class AutocompleteCombobox(ttk.Combobox):
    """Combobox con supporto per l'autocompletamento.

    Utilizzare set_completion_list() per impostare la lista dei
    modelli disponibili. L'evento di tastiera filtra le opzioni in
    base al testo digitato.
    """

    def __init__(self, master: tk.Misc | None = None, **kwargs: Any):
        super().__init__(master, **kwargs)
        self._completion_list: list[str] = []
        # Vincoliamo l'evento di rilascio del tasto per filtrare le opzioni
        self.bind("<KeyRelease>", self._on_keyrelease)

    def set_completion_list(self, completion_list: list[str]) -> None:
        """Imposta la lista di modelli disponibili e aggiorna i valori.

        La lista viene ordinata per rendere la ricerca più prevedibile.
        """
        # Copia e ordina le voci per un confronto case-insensitive
        self._completion_list = sorted(completion_list, key=lambda s: s.lower())
        # Aggiorna le opzioni della combobox
        self["values"] = self._completion_list

    def _on_keyrelease(self, event: tk.Event) -> None:
        """Filtra l'elenco delle opzioni in base al testo digitato."""
        # Non filtrare se la lista è vuota
        if not self._completion_list:
            return
        # Testo attualmente digitato
        typed = self.get()
        # Determina le voci che contengono il testo digitato (ignorando il
        # maiuscolo/minuscolo)
        if typed:
            data = [item for item in self._completion_list if typed.lower() in item.lower()]
        else:
            data = self._completion_list
        # Aggiorna l'elenco delle opzioni mostrate nella combobox
        self["values"] = data
        # Se c'è almeno una voce corrispondente, apri il menu a discesa
        if data:
            # Visualizza la lista a discesa
            self.event_generate("<Down>")



class GlocalAiConfrontoGUI:
    """Classe principale per la finestra dell’interfaccia grafica."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Glocal AI Confronto")
        # Aumentiamo la dimensione iniziale della finestra per visualizzare
        # meglio il campo del modello, soprattutto quando i nomi dei modelli
        # sono lunghi.  Rendiamo la finestra anche ridimensionabile in modo
        # che gli utenti possano adattarla a piacere.
        self.root.geometry("600x300")
        self.root.resizable(True, True)

        # Percorso del file selezionato
        self.file_path_var = tk.StringVar()

        # Metodo di estrazione selezionato
        self.method_var = tk.StringVar(value="both")

        # Provider e modello per LLM
        # provider_var conterrà il nome del provider selezionato (es. "openai" oppure "openrouter").
        self.provider_var = tk.StringVar(value="openai")
        # model_var memorizza il modello LLM da utilizzare. Verrà popolato in modo dinamico
        # quando l'utente seleziona il provider. Inizialmente impostiamo un valore di default.
        self.model_var = tk.StringVar(value="gpt-3.5-turbo")

        # Creazione interfaccia
        self.create_widgets()

    # ------------------------------------------------------------------
    # Utility: restituisce la lista dei modelli disponibili per un dato
    # provider. La chiamata può richiedere pochi secondi perché interroga
    # le API remote di OpenAI o OpenRouter. In caso di errore o di
    # mancanza delle chiavi API corrispondenti, viene restituita una lista
    # vuota. Le risposte vengono filtrate per includere solo modelli
    # compatibili con le chat (id che contengono "gpt" per OpenAI).
    def fetch_models_for_provider(self, provider: str) -> list[str]:
        provider = provider.lower() if provider else ""
        # OpenAI: ottieni l'elenco dei modelli tramite l'API ufficiale
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return []
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                models = resp.json().get("data", [])
                # Filtra solo i modelli con id che contengono "gpt" per evitare
                # embedding e modelli legacy
                names: list[str] = []
                for m in models:
                    model_id = m.get("id", "")
                    if "gpt" in model_id:
                        names.append(model_id)
                return sorted(names)
            except Exception:
                return []

        # OpenRouter: ottieni l'elenco dei modelli tramite l'API di OpenRouter
        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return []
            url = "https://openrouter.ai/api/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json().get("data", [])
                names: list[str] = []
                for m in data:
                    # Ogni entry può contenere id, canonical_slug o slug
                    model_id: str | None = None
                    # Le chiavi possono variare: id, canonical_slug, slug, name
                    for key in ("id", "canonical_slug", "slug", "name"):
                        if key in m and m[key]:
                            model_id = m[key]
                            break
                    if model_id:
                        names.append(str(model_id))
                return sorted(names)
            except Exception:
                return []
        return []

    # Aggiorna l'elenco dei modelli quando cambia il provider.  Questa
    # funzione avvia un thread per non bloccare la GUI durante la
    # richiesta di rete e poi aggiorna la combobox con i risultati.
    def update_model_list(self) -> None:
        provider = self.provider_var.get()
        # Esegui la chiamata in un thread separato
        def worker() -> None:
            models = self.fetch_models_for_provider(provider)
            # Aggiorna la combobox sul thread principale
            def update_ui() -> None:
                # Memorizza la lista completa dei modelli
                self.model_full_list = models
                # Aggiorna la combobox con l'elenco filtrato in base al filtro
                self.apply_filter_to_models()
                # Se l'elenco non è vuoto e il valore corrente non è presente,
                # selezioniamo il primo modello come predefinito
                current = self.model_var.get()
                if self.model_full_list and current not in self.model_full_list:
                    # Imposta come selezionato il primo modello della lista completa
                    self.model_var.set(self.model_full_list[0])
            try:
                self.root.after(0, update_ui)
            except Exception:
                pass
        # Avvia il thread
        threading.Thread(target=worker, daemon=True).start()

    # Callback eseguito quando l'utente cambia provider.  Aggiorna
    # dinamicamente la lista dei modelli.
    def on_provider_changed(self, event: tk.Event | None = None) -> None:
        self.update_model_list()

    def apply_filter_to_models(self) -> None:
        """Applica il filtro inserito dall'utente per aggiornare la lista dei modelli.

        Il filtro viene recuperato da ``self.filter_var`` e confrontato in
        modo case-insensitive con l'id del modello. I modelli che
        contengono la stringa di ricerca vengono mostrati nel menu a
        tendina. Se il modello attualmente selezionato non è più
        disponibile nella lista filtrata, viene selezionato il primo
        modello disponibile (se presente).
        """
        query = self.filter_var.get().strip().lower()
        if query:
            filtered = [m for m in self.model_full_list if query in m.lower()]
        else:
            filtered = list(self.model_full_list)
        # Aggiorna le opzioni della combobox
        try:
            self.model_combo.config(values=filtered)
        except Exception:
            pass
        # Se il modello corrente non è presente tra quelli filtrati,
        # selezioniamo il primo elemento disponibile
        current = self.model_var.get()
        if current not in filtered:
            if filtered:
                self.model_var.set(filtered[0])
            else:
                self.model_var.set("")

    def on_filter_changed(self, event: tk.Event | None = None) -> None:
        """Gestisce l'aggiornamento della lista dei modelli quando cambia il filtro."""
        self.apply_filter_to_models()

    def log(self, message: str) -> None:
        """Aggiunge una riga al log visualizzato nella GUI.

        Il log viene mantenuto come testo solo in append e non può essere
        modificato direttamente dall'utente. Ogni messaggio viene
        automaticamente portato in vista.
        """
        try:
            # Permetti l'inserimento del testo
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            # Blocca nuovamente l'area di testo
            self.log_text.config(state=tk.DISABLED)
        except Exception:
            pass

    def create_widgets(self) -> None:
        """Crea e dispone i widget dell’interfaccia."""
        # Selettore file
        file_frame = ttk.Frame(self.root)
        file_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(file_frame, text="File PDF:").pack(side=tk.LEFT)
        entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=40)
        entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Sfoglia…", command=self.select_file).pack(side=tk.LEFT)

        # Opzioni metodo
        method_frame = ttk.LabelFrame(self.root, text="Metodo di estrazione")
        method_frame.pack(fill=tk.X, padx=10, pady=10)
        # Radiobuttons con callback per abilitare/disabilitare le opzioni LLM
        for value, label in (("google", "Google Document AI"), ("chatgpt", "ChatGPT/LLM"), ("both", "Entrambi")):
            ttk.Radiobutton(
                method_frame,
                text=label,
                variable=self.method_var,
                value=value,
                command=self.update_llm_options_state,
            ).pack(side=tk.LEFT, padx=5, pady=5)

        # Frame per la scelta del provider, filtro e modello LLM.
        # Utilizziamo una griglia per poter assegnare pesi alle colonne e
        # gestire l'espansione orizzontale del campo modello quando la
        # finestra viene ridimensionata.
        llm_frame = ttk.LabelFrame(self.root, text="Opzioni LLM")
        llm_frame.pack(fill=tk.BOTH, padx=10, pady=10, expand=True)
        # Configuriamo le colonne della griglia: le colonne 3 e 4 hanno peso
        # affinché le entry (filtro e combobox del modello) si allarghino
        # quando la finestra viene ridimensionata.
        for col in (0, 1, 2, 3, 4):
            llm_frame.columnconfigure(col, weight=0)
        llm_frame.columnconfigure(3, weight=1)  # campo filtro
        llm_frame.columnconfigure(4, weight=1)  # campo modello

        # RIGA 0: Provider e Filtro modello
        ttk.Label(llm_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        providers = ["openai", "openrouter"]
        self.provider_combo = ttk.Combobox(
            llm_frame,
            textvariable=self.provider_var,
            values=providers,
            state="readonly"
        )
        self.provider_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        # Lega il cambio di provider all'aggiornamento dei modelli
        self.provider_combo.bind("<<ComboboxSelected>>", self.on_provider_changed)

        # Filtro per cercare il modello.  L'utente può digitare parte del nome
        # di un modello e la lista dei modelli verrà filtrata di
        # conseguenza.
        ttk.Label(llm_frame, text="Cerca modello:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(llm_frame, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=3, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        # Quando si digita nel filtro, aggiorna l'elenco dei modelli
        self.filter_entry.bind("<KeyRelease>", self.on_filter_changed)

        # RIGA 1: Selettore del modello.  Il combobox si espande
        # orizzontalmente grazie alla colonna 4 configurata con peso.
        ttk.Label(llm_frame, text="Modello:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        # Utilizziamo un combobox classico (readonly).  La lista dei modelli
        # verrà popolata dinamicamente e il valore selezionato verrà
        # sincronizzato tramite model_var.
        self.model_combo = ttk.Combobox(
            llm_frame,
            textvariable=self.model_var,
            values=[],
            state="readonly"
        )
        self.model_combo.grid(row=1, column=1, columnspan=4, sticky=tk.EW, padx=5, pady=5)

        # Memorizzeremo la lista completa dei modelli restituiti dal provider
        self.model_full_list: list[str] = []
        # Carichiamo immediatamente la lista dei modelli per il provider di default
        self.update_model_list()
        # Disabilita opzioni se il metodo non include LLM
        self.update_llm_options_state()

        # ------------------------------------------------------------------
        # Sezioni aggiuntive (Costi e Log)
        # Questi frame vengono creati una sola volta e servono a mostrare
        # il costo stimato delle chiamate e il log delle operazioni.
        # Frame per i costi
        self.cost_frame = ttk.LabelFrame(self.root, text="Costi")
        self.cost_frame.pack(fill=tk.X, padx=10, pady=5)
        self.total_cost: float = 0.0
        self.cost_label = ttk.Label(self.cost_frame, text="Costo totale stimato: --")
        self.cost_label.pack(anchor="w", padx=5, pady=5)

        # Frame per i log
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)
        # Importiamo scrolledtext per avere una scrollbar integrata
        try:
            from tkinter import scrolledtext
            self.log_text: tk.Text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=6)
        except Exception:
            self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=6)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

    def update_llm_options_state(self) -> None:
        """Abilita o disabilita le opzioni LLM in base al metodo selezionato."""
        method = self.method_var.get()
        # se il metodo include LLM, abilita; altrimenti disabilita
        state = "readonly" if method in ("chatgpt", "both") else "disabled"
        entry_state = "normal" if method in ("chatgpt", "both") else "disabled"
        # Provider
        try:
            self.provider_combo.config(state=state)
        except Exception:
            pass
        # Model
        try:
            self.model_combo.config(state=entry_state)
        except Exception:
            pass

        # Se ora le opzioni LLM sono abilitate e la combobox dei modelli
        # non contiene ancora dati, popoliamo la lista. Questo viene
        # eseguito quando l'utente passa da un metodo che non usa LLM a
        # uno che lo usa (chatgpt o both).
        if method in ("chatgpt", "both") and not self.model_combo.cget("values"):
            self.update_model_list()

        # Pulsante avvio. Per evitare di ricrearlo ad ogni aggiornamento,
        # verifichiamo se esiste già. Se non esiste, lo creiamo.
        if not hasattr(self, "action_frame"):
            self.action_frame = ttk.Frame(self.root)
            self.action_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Button(
                self.action_frame,
                text="Avvia estrazione",
                command=self.run_extraction
            ).pack(side=tk.LEFT)


    def select_file(self) -> None:
        """Apre una finestra di dialogo per selezionare il file PDF."""
        file_path = filedialog.askopenfilename(
            title="Seleziona un file PDF",
            filetypes=[("PDF", "*.pdf")]
        )
        if file_path:
            self.file_path_var.set(file_path)

    def run_extraction(self) -> None:
        """Esegue l’estrazione secondo le opzioni selezionate e salva i risultati su file."""
        file_path = self.file_path_var.get().strip()
        if not file_path or not os.path.isfile(file_path):
            messagebox.showerror("Errore", "Per favore seleziona un file PDF valido.")
            return
        method = self.method_var.get()

        # Directory e nome base del file PDF
        directory = os.path.dirname(file_path)
        base_name, _ = os.path.splitext(os.path.basename(file_path))

        # Timestamp per i nomi dei file
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        saved_files = []

        # Log: inizio estrazione
        self.log(f"Inizio estrazione per il file: {file_path}")

        # Azzeriamo il costo totale stimato per questa sessione
        self.total_cost = 0.0

        # Esecuzione Document AI e salvataggio
        if method in ("google", "both"):
            try:
                result = extract_with_google_document_ai(file_path)
                out_name = f"{base_name}_google_{timestamp}.json"
                out_path = os.path.join(directory, out_name)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                saved_files.append(out_path)
                # Log
                self.log(f"Document AI completato: file salvato come {out_name}")
                # Aggiorna il costo (placeholder: costo non calcolato)
                # In futuro si potrà calcolare il costo in base alle API
                # Document AI. Al momento viene aggiunto zero.
                self.total_cost += 0.0
            except Exception as e:
                messagebox.showerror("Errore Document AI", f"Errore durante l'estrazione con Document AI:\n{e}")
                self.log(f"Errore Document AI: {e}")

        # Esecuzione ChatGPT/LLM e salvataggio
        if method in ("chatgpt", "both"):
            try:
                # Leggi provider e modello selezionati
                provider = self.provider_var.get().strip() or "openai"
                model = self.model_var.get().strip() or "gpt-3.5-turbo"
                result = extract_with_chatgpt(file_path, model=model, provider=provider)
                # Genera un nome file che includa provider e modello per distinguere l'LLM utilizzato
                provider_clean = provider.replace(" ", "-") if provider else "llm"
                model_clean = model.replace(" ", "-") if model else "model"
                out_name = f"{base_name}_{provider_clean}_{model_clean}_{timestamp}.json"
                out_path = os.path.join(directory, out_name)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                saved_files.append(out_path)
                # Log
                self.log(f"LLM completato ({provider}/{model}): file salvato come {out_name}")
                # Aggiorna il costo stimato (placeholder a 0).  Se in futuro si
                # desidera calcolare il costo in base ai token utilizzati
                # dall'LLM, si potrà aggiornare questa linea.
                self.total_cost += 0.0
            except Exception as e:
                messagebox.showerror("Errore ChatGPT", f"Errore durante l'estrazione con il LLM:\n{e}")
                self.log(f"Errore LLM: {e}")

        if saved_files:
            # Log file salvati
            self.log("Operazione completata. File generati:")
            for fp in saved_files:
                self.log(f"  - {os.path.basename(fp)}")
            # Apri la cartella di destinazione nel file manager
            folder = directory
            try:
                import sys
                import subprocess
                if sys.platform.startswith("win"):  # Windows
                    os.startfile(folder)
                elif sys.platform == "darwin":  # macOS
                    subprocess.call(["open", folder])
                else:  # Linux / altri
                    subprocess.call(["xdg-open", folder])
            except Exception:
                pass
            # Facoltativamente mostra un messaggio di completamento
            messagebox.showinfo(
                "Estrazione completata",
                f"File JSON generato{'i' if len(saved_files) > 1 else ''} in:\n"
                + "\n".join(saved_files)
            )
            # Aggiorna la label dei costi con il costo totale stimato
            self.cost_label.config(text=f"Costo totale stimato: € {self.total_cost:.4f}")

    def show_result_window(self, text: str) -> None:
        """Mostra il risultato in una nuova finestra con possibilità di salvataggio."""
        win = tk.Toplevel(self.root)
        win.title("Risultato estrazione")
        win.geometry("600x400")

        # Text widget con scrollbar
        text_widget = tk.Text(win, wrap=tk.NONE)
        vsb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=text_widget.yview)
        hsb = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        text_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        text_widget.insert(tk.END, text)
        text_widget.config(state=tk.DISABLED)

        # Bottone per salvare il risultato su file
        def save_to_file() -> None:
            file_path = filedialog.asksaveasfilename(
                title="Salva risultato",
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("Tutti i file", "*.*")]
            )
            if file_path:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    messagebox.showinfo("Salvataggio", f"File salvato in:\n{file_path}")
                except Exception as e:
                    messagebox.showerror("Errore", f"Impossibile salvare il file:\n{e}")

        ttk.Button(win, text="Salva su file…", command=save_to_file).pack(side=tk.BOTTOM, pady=5)


def main() -> None:
    root = tk.Tk()
    app = GlocalAiConfrontoGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()