from cat.mad_hatter.decorators import hook
from .rabbit_hole import RabbitHole

@hook
def after_cat_bootstrap(caller):
    # Rabbit Hole Instance
    caller.rabbit_hole = RabbitHole(caller)  # TODOV2: check if it works, I guess not yet