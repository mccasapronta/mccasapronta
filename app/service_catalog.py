
from dataclasses import dataclass
from typing import List, Dict

@dataclass(frozen=True)
class ServiceItem:
    code: str
    label: str
    price_eur: float  # base price per item selection

# Define catalog grouped by category
CATALOG: Dict[str, List[ServiceItem]] = {
    "Limpeza Geral": [
        ServiceItem("geral_chao", "Aspiração e lavagem de chão", 10.0),
        ServiceItem("geral_po", "Tirar pó (superfícies, móveis)", 8.0),
        ServiceItem("geral_cozinha", "Limpeza de cozinha (bancadas, fogão, eletrodomésticos por fora)", 12.0),
        ServiceItem("geral_wc", "Limpeza de casas de banho (sanita, lavatório, duche/banheira)", 12.0),
        ServiceItem("geral_lixo", "Recolha de lixo e reciclagem", 5.0),
    ],
    "Limpeza Profunda": [
        ServiceItem("prof_janelas", "Janelas (interior e exterior)", 15.0),
        ServiceItem("prof_detalhes", "Rodapés, portas, interruptores", 10.0),
        ServiceItem("prof_desinf", "Desinfeção completa de cozinha e WC", 20.0),
        ServiceItem("prof_chao", "Aspiração e lavagem de chão", 10.0),
        ServiceItem("prof_po", "Tirar pó (superfícies, móveis)", 8.0),
        ServiceItem("prof_lixo", "Recolha de lixo e reciclagem", 5.0),
        
    ],
    "Limpeza Especial": [
        ServiceItem("esp_pos_obra", "Pós-obra / pós-renovação", 35.0),
        ServiceItem("esp_mudanca", "Limpeza de mudança (entrada/saída)", 30.0),
        ServiceItem("esp_frio", "Limpeza interna de frigorífico/congelador", 10.0),
        ServiceItem("esp_forno", "Limpeza de forno, micro-ondas, exaustor", 12.0),
        ServiceItem("esp_armarios", "Armários por dentro (cozinha ou roupeiros)", 14.0),
        ServiceItem("esp_exterior", "Varandas, terraços ou churrasqueiras", 12.0),
    ],
}

def get_item(code: str) -> ServiceItem | None:
    for items in CATALOG.values():
        for it in items:
            if it.code == code:
                return it
    return None

def calculate_total(selected_codes: List[str]) -> float:
    total = 0.0
    for code in selected_codes:
        it = get_item(code)
        if it:
            total += it.price_eur
    return total
