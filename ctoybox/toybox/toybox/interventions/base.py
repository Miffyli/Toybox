from abc import ABC, abstractmethod
from toybox.toybox import Toybox
import inspect
import json
""" Contains the base class for interventions. 

To make interventions for a new game, subclass Intervention."""

class BaseMixin(ABC):
  """Base class for game objects. Registers mutation so JSON can be pushed via context manager."""

  @classmethod
  @property
  @abstractmethod
  def expected_keys(clz): pass

  def __init__(self, *args, **kwargs):
    self.intervention = None
    # super().__init__(*args, **kwargs) 

  def __setattr__(self, name, value):
    calling_fn = inspect.stack()[1].function
    existing_attrs = self.__dict__.keys()
    adding_new = name not in existing_attrs
    # Prohibit adding fields outside object instantiation/initialization
    if calling_fn != '__init__' and calling_fn != '__setattr__':
      if adding_new:
        raise AttributeError("Cannot add new fields to %s from %s" % (self.__class__.__name__, calling_fn))
      assert 'intervention' in existing_attrs
      self.intervention.dirty_state = True
    super().__setattr__(name, value)
  
  def decode(intervention, obj, clz):
    """Creates an instance of the input class from the JSON. 
    
    All game elements inherit from BaseMixin. `decode` should be called recursively. 

    Parameters
    ---
    intervention : Intervention
      The context manager
    obj : json
      The input JSON blob
    clz : Class
      The subclass being instantiated

    Returns
    ---
    BaseMixin
      A subclass of BaseMixin corresponding to a game or game element. 
    
    """
    actual_keys = set(obj.keys()) 
    target_name = clz.__name__
    intersection = actual_keys.intersection(clz.expected_keys)
    not_enough = len(clz.expected_keys) > len(intersection)
    too_many = len(actual_keys) > len(intersection)

    if not_enough:
      raise ValueError("Missing keys; maybe %s is not a %s object?" % (
        json.dumps(obj), target_name))

    elif too_many:
      raise ValueError("Input object contains too many keys (%s); has the specification for %s changed?" % (
        str(actual_keys), target_name))

    else: return clz(intervention, **obj)        


  def encode(self):
    dat = {}
    for name, val in self.__dict__.items():
      if name not in self.expected_keys:
        continue
      dat[name] = val.encode() if isinstance(val, BaseMixin) else val
    return dat
        

class Game(BaseMixin):
  """Base class for games. Supertype that contains common elements."""

  expected_keys = ['score', 'player', 'lives', 'rand', 'level']

  def __init__(self, intervention, score, player, lives, rand, level, *args, **kwargs):
    print('Game init')
    self.score = score
    self.player = player
    self.rand = rand
    self.lives = lives
    self.level = level
    self.intervention = intervention
  

class Direction(BaseMixin):

  Up    = 'Up'
  Down  = 'Down'
  Left  = 'Left'
  Right = 'Right'

  directions = [Up, Down, Left, Right]

  def __init__(self, intervention, direction):
    self.intervention = intervention
    assert direction in Direction.directions
    self.direction = direction

  def decode(intervention, direction, clz):
    return Direction(intervention, direction)

  def encode(self):
    return self.direction


class Intervention(ABC):

  def __init__(self, tb, game_name, clz):
    print('Initializing intervention')
    # for frame in inspect.stack():
    #   print(frame.function)
    # check that the simulation in tb matches the game name.
    self.toybox = tb
    # self.state = None
    self.config = None
    self.dirty_config = False
    self.dirty_state = False
    self.game_name = game_name
    assert tb.game_name == game_name
    self.clz = clz
    self.game = None

  def __enter__(self):
    # grab the JSON to be manipulated
    # self.state = self.toybox.to_state_json()
    self.config = self.toybox.config_to_json()
    self.game = self.clz.decode(self, self.toybox.to_state_json(), self.clz)

    return self

  def __exit__(self, exec_type, exc_value, traceback):
    # commit the JSON
    
    if self.dirty_config:
      assert False
      self.toybox.write_config_json(self.config)
      # print("new_game!")
      self.toybox.new_game()

    elif self.dirty_state:
      print("write_state_json!")
      self.toybox.write_state_json(self.game.encode())

    self.config = None


  def set_partial_config(self, fname): 
    import os

    if os.path.isfile(fname): 
      with open(fname) as f:
          data = json.load(f)
          for k in data.keys(): 
            if k in self.config.keys():
              self.config[k] = data[k]
              self.dirty_config = True


if __name__ == "__main__":
  with Toybox('amidar') as tb:
    state = tb.to_state_json()
    config = tb.config_to_json()
    
    with Intervention(tb, 'amidar') as intervention:
      intervention.config['enemies'] = []

      new_state = intervention.state
      new_config = intervention.config

    assert len(config['enemies']) == 5
    assert len(new_config['enemies']) == 0
    assert len(tb.config_to_json()['enemies']) == 0

