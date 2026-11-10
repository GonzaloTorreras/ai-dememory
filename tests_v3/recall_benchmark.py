"""Synthetic vocabulary holdout; not a production or semantic benchmark."""
import json
import tempfile
from pathlib import Path
from ai_dememory.search import SearchIndex
from ai_dememory.vault import Vault

# Independently proposed before implementing the source-wording search change.
# kind, title, canonical claim, literal evidence, query
CASES = [
    ("source", "Nerea storage rule", "Nerea keeps four spare keys in the blue drawer.", "Guardo cuatro llaves de repuesto en el cajón azul.", "llaves cajón"),
    ("source", "Bruno grain delivery", "Bruno needs seven sacks of rye before dawn.", "Para Bruno hacen falta siete sacos de centeno antes del amanecer.", "centeno amanecer"),
    ("source", "Clara orchard routine", "Clara chains the orchard gate after sunset and checks it every two weeks.", "La verja del huerto queda encadenada después del anochecer y Clara la revisa cada dos semanas.", "verja anochecer"),
    ("source", "Utensilios de Damián", "Damián usa una cuchara de latón para el tarro de miel y deja ambos en el estante superior.", "Damián uses one brass spoon for the honey jar and keeps both on the upper shelf.", "brass honey"),
    ("source", "Secado de Ona", "Los guantes de repuesto de Ona deben secarse dentro de casa durante cuarenta y ocho horas antes de guardarlos.", "Ona's spare gloves must dry indoors for forty-eight hours before packing.", "gloves indoors"),
    ("source", "Bancal de Teo", "Teo quita las malas hierbas del bancal norte cada tres días y nunca con el suelo mojado.", "Teo pulls weeds from the north bed every three days, never on wet ground.", "weeds wet"),
    ("translation", "Helena cold storage", "Helena keeps butter below six degrees overnight.", "Keep the butter below six degrees overnight.", "mantequilla seis grados"),
    ("translation", "Costura de Beatriz", "Beatriz debe devolver tres agujas antes del jueves a las diez.", "Tengo que devolver tres agujas antes del jueves a las diez.", "three needles Thursday"),
    ("translation", "Rafael roof safety", "Rafael keeps the roof hatch shut with five bolts until Friday morning.", "The roof hatch must stay shut with five bolts until Friday morning.", "escotilla viernes"),
    ("translation", "Cuidados de Inés", "Inés lava la manta azul a mano con agua fría una vez al mes.", "Lava la manta azul a mano con agua fría una vez al mes.", "blue blanket monthly"),
    ("negative", "Marta ferry departure", "Marta's ferry leaves from the west pier at eight thirty.", "El barco de Marta sale del muelle oeste a las ocho y media.", "barco muelle este nueve"),
    ("negative", "Lidia equipment return", "Lidia returns eight shovels to the northern shed.", "Lidia devuelve ocho palas al cobertizo norte.", "Sofía devuelve cinco palas"),
]


def measure():
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        for i, (kind, title, content, evidence, query) in enumerate(CASES):
            vault = Vault.create(Path(temporary) / str(i))
            memory = vault._remember(content, title, source={"provider":"fixture", "session":"s", "turn":str(i),
                                      "evidence_kind":"user_statement", "excerpt":evidence})
            index = SearchIndex(vault)
            before = any(h.memory_id == memory.memory_id for h in index.search(query, include_source=False))
            after = any(h.memory_id == memory.memory_id for h in index.search(query, include_source=True))
            results.append({"case":i, "kind":kind, "before":before, "after":after})
    return {"source_vocabulary":{"cases":6, "before":sum(r["before"] for r in results if r["kind"] == "source"),
                                "after":sum(r["after"] for r in results if r["kind"] == "source")},
            "translation_ceiling":{"cases":4, "after":sum(r["after"] for r in results if r["kind"] == "translation")},
            "wrong_constraint_matches":{"cases":2, "after":sum(r["after"] for r in results if r["kind"] == "negative")},
            "model_calls":0}


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
