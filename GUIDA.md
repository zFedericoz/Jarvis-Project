# JARVIS — Guida al potenziamento

## File consegnati

| File | Sostituisce | Cosa cambia |
|------|-------------|-------------|
| `persona.yaml` | `backend/config/persona.yaml` | System prompt più ricco, 10 esempi few-shot, istruzioni RAG/memoria esplicite |
| `multiagent.py` | `backend/brain/multiagent.py` | RAG con soglia di rilevanza, budget contesto, reflection selettiva |
| `dataset_finetune.jsonl` | *(nuovo file)* | 70 coppie input/output per fine-tuning Qwen 2.5 |

---

## 1. Sostituire i file

```bash
# Dal PC, copia i file nel progetto
cp persona.yaml    /percorso/JARVIS/backend/config/persona.yaml
cp multiagent.py   /percorso/JARVIS/backend/brain/multiagent.py

# Riavvia il backend
docker compose restart backend
```

---

## 2. Popolare la knowledge base (RAG)

Copia i tuoi documenti nella cartella di watch:

```bash
# Esempi di documenti utili
cp ARCHITECTURE.md         backend/data/knowledge/
cp README.md               backend/data/knowledge/
cp docs/api_reference.md   backend/data/knowledge/
# PDF, TXT, PY, JSON, YAML sono tutti supportati
```

Indicizzazione immediata:
```bash
docker exec jarvis-backend python -m memory.rag_indexer index data/knowledge/
docker exec jarvis-backend python -m memory.rag_indexer stats
```

La soglia di rilevanza nel nuovo `multiagent.py` è `_RAG_DISTANCE_THRESHOLD = 1.2`.
Se vuoi risposte più conservative (solo chunk molto rilevanti) abbassala a `0.9`.

---

## 3. Fine-tuning con Unsloth (opzionale ma consigliato)

### Requisiti
- GPU NVIDIA con almeno 8 GB VRAM (RTX 3060 o superiore)
- Python 3.10+ con CUDA

### Setup
```bash
pip install unsloth
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Script di fine-tuning

Salva questo come `finetune.py` ed eseguilo sul PC host (non nel container):

```python
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# Carica il modello base (deve essere già scaricato da Ollama)
# Unsloth supporta direttamente i modelli GGUF/HF
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-14B-Instruct",  # o il percorso locale
    max_seq_length=2048,
    load_in_4bit=True,      # quantizzazione 4-bit per risparmiare VRAM
)

# Aggiungi LoRA adapters (fine-tuning efficiente)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                   # rank LoRA — più alto = più parametri, più lento
    target_modules=["q_proj", "v_proj"],
    lora_alpha=16,
    lora_dropout=0.05,
)

# Formatta il dataset nel template Alpaca
ALPACA_TEMPLATE = """Di seguito è riportata un'istruzione che descrive un compito. Scrivi una risposta che completi adeguatamente la richiesta.

### Istruzione:
{instruction}

### Input:
{input}

### Risposta:
{output}"""

dataset = load_dataset("json", data_files="dataset_finetune.jsonl", split="train")

def format_example(example):
    return {"text": ALPACA_TEMPLATE.format(**example)}

dataset = dataset.map(format_example)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        num_train_epochs=3,
        learning_rate=2e-4,
        fp16=True,
        output_dir="./jarvis_finetuned",
        logging_steps=10,
        save_steps=100,
    ),
)

trainer.train()

# Salva il modello fine-tunato
model.save_pretrained_gguf(
    "jarvis_finetuned_gguf",
    tokenizer,
    quantization_method="q4_k_m",  # buon bilanciamento qualità/dimensione
)
```

### Caricare il modello fine-tunato su Ollama

```bash
# Crea un Modelfile
cat > Modelfile << 'EOF'
FROM ./jarvis_finetuned_gguf/model.gguf
SYSTEM "You are J.A.R.V.I.S. — Just Another Rather Very Intelligent System."
PARAMETER temperature 0.3
PARAMETER num_ctx 4096
EOF

# Importa in Ollama
ollama create jarvis-ft:v1 -f Modelfile

# Aggiorna settings.yaml
# llm:
#   model: jarvis-ft:v1
```

---

## 4. Espandere il dataset

Il dataset attuale ha 70 esempi. Per un fine-tuning di qualità servono almeno 200-500.
Aggiungi esempi coprendo i tuoi casi d'uso reali:

```jsonl
{"instruction": "la tua domanda reale", "input": "contesto opzionale", "output": "risposta ideale di JARVIS"}
```

Suggerimenti per espandere:
- Registra le conversazioni dove JARVIS risponde bene → trasformale in esempi
- Aggiungi varianti delle stesse domande (sinonimi, typo, formulazioni diverse)
- Copri i casi edge: domande ambigue, errori, richieste fuori scope

---

## 5. Verificare che tutto funzioni

```bash
# Test RAG
docker exec jarvis-backend python -m memory.rag_indexer stats

# Test sistema
curl -X POST http://localhost:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "cosa puoi fare?"}'

# Log in tempo reale
docker logs -f jarvis-backend | grep -E "RAG|reflection|context"
```
