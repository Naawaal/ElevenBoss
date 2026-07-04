import random
from dataclasses import dataclass

@dataclass
class GeneratedBotClub:
    name: str
    short_name: str
    budget: int = 10000000
    reputation: int = 500
    stadium_capacity: int = 10000

BOT_NAME_TEMPLATES = [
    ("Ironvale FC", "IVF"),
    ("Northbridge United", "NBU"),
    ("Emerald City Athletic", "ECA"),
    ("Riverside Rovers", "RSR"),
    ("Crownfield Town", "CFT"),
    ("Stormgate FC", "SGFC"),
    ("Silverline Albion", "SLA"),
    ("Eastford Wanderers", "EFW"),
    ("Oakwood Town", "OWT"),
    ("Blackwood FC", "BWFC"),
    ("Southwater Athletic", "SWA"),
    ("Westbury Rovers", "WBR"),
    ("Kingsport City", "KPC"),
    ("Cresthaven United", "CHU"),
    ("Millstone Town", "MST"),
    ("Stonebridge FC", "SBFC"),
    ("Redwood Rangers", "RWR"),
    ("Sunvale Albion", "SVA"),
    ("Deepford Wanderers", "DFW"),
    ("Highland Athletic", "HLA")
]

def generate_bot_clubs_data(
    guild_id: str,
    count: int,
    existing_names: set[str]
) -> list[GeneratedBotClub]:
    """
    Generate unique bot club names, budgets, reputations, and capacities.
    """
    generated = []
    # Normalize existing names for case-insensitive comparison
    existing_normalized = {n.lower() for n in existing_names}
    
    available_templates = [t for t in BOT_NAME_TEMPLATES if t[0].lower() not in existing_normalized]
    
    # Shuffle to ensure variety
    random.shuffle(available_templates)
    
    # Track names generated in this call
    generated_names = set()
    
    for i in range(count):
        if i < len(available_templates):
            name, short_name = available_templates[i]
            generated.append(
                GeneratedBotClub(
                    name=name,
                    short_name=short_name,
                    budget=10000000,
                    reputation=500,
                    stadium_capacity=10000
                )
            )
            generated_names.add(name.lower())
        else:
            # Fallback if we run out of unique names
            # Find a suffix A, B, C, ... AA, AB, ... such that the name is unique
            suffix_num = i - len(available_templates) + 1
            while True:
                # convert suffix_num to letter representation (1=A, 2=B, ..., 27=AA, etc.)
                letter_representation = ""
                temp_num = suffix_num
                while temp_num > 0:
                    temp_num, remainder = divmod(temp_num - 1, 26)
                    letter_representation = chr(65 + remainder) + letter_representation
                
                name = f"Bot Club {letter_representation}"
                short_name = f"BC{letter_representation}"
                if name.lower() not in existing_normalized and name.lower() not in generated_names:
                    break
                suffix_num += 1
            
            generated.append(
                GeneratedBotClub(
                    name=name,
                    short_name=short_name,
                    budget=10000000,
                    reputation=500,
                    stadium_capacity=10000
                )
            )
            generated_names.add(name.lower())
        
    return generated
