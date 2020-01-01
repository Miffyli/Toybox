import toybox.testing.envs.gym as gym
import toybox.testing.models.openai_baselines as oai
import toybox.interventions.amidar as ami
import toybox.testing.behavior as behavior
import os
import random
import time
import tensorflow as tf

from scipy.stats import sem
from numpy import mean
from abc import abstractmethod

# These tests all share the same setup
# This used to be in a separate module. 
# We may want to consider putting it back into a separate module, since
# we cannot currently use the automated tools for test discovery with an 
# abstract test. There is probably a way to configure this.
class AmidarToyboxTestBase(behavior.BehavioralFixture):
  
    @classmethod
    def setUpEnv(cls):
      seed = 0xdeadbeef
      gym.setUpToyboxGym(cls, 'AmidarToyboxNoFrameskip-v4', seed)
    
    @classmethod
    def tearDownEnv(cls):
      gym.tearDownToyboxGym(cls)

    def takeAction(self, model):
      oai.takeAction(self, model)

    def stepEnv(self):
      gym.stepEnv(self)

    def resetEnv(self):
      gym.resetEnv(self)

    def isDone(self):
      lives = self.toybox.get_lives()
      has_reset = lives > self.lives
      self.lives = lives
      #print('lives', lives, 'has_reset',  has_reset, 'hasTimedOut', self.hasTimedOut())
      return self.hasTimedOut() or has_reset

    @abstractmethod
    def intervene(self): assert False


class EnemyRemovalTest(AmidarToyboxTestBase):

    def setUp(self):
        # remember, setup applies to 
        super().setUp(trials=5, timeout=500)

    def shouldIntervene(self):
        return self.tick == 0

    def onTrialEnd(self):
      # An agent trained on ALE should be able to complete at least half of 
      # level 1 before time.
      with ami.AmidarIntervention(self.getToybox()) as intervention:
        painted = len(intervention.filter_tiles(lambda t: t.tag == ami.Tile.Painted))
        self.assertGreaterEqual(painted, 10)
        print('painted:', painted, 'score', intervention.game.score)
        return {'painted': painted, 'score' : intervention.game.score}

    def onTestEnd(self): pass

    def intervene(self):
      with ami.AmidarIntervention(self.getToybox()) as intervention:
        intervention.game.lives = 1
        intervention.game.enemies.clear()

    def test_no_enemies_ppo2(self):
        print('testing test_no_enemies_ppo2')
        seed = 42
        # fdir = os.path.dirname(os.path.abspath(__file__))
        # path = os.sep.join([fdir, 'models', 'AmidarNoFrameskip-v4.ppo2.5e7.845090117.2018-12-29.model'])  
        path = '../models/AmidarToyboxNoFrameskip-v4.regress.model'
        # # You need to do this if you want to load more than one model with tensorflow
        with tf.Session(graph=tf.Graph()):
            model = oai.getModel(self.env, 'ppo2', seed, path)
            # Set low to be a test of a test!
            self.runTest(model)

    def test_no_enemies_all_models(self):
        seed = 42
        fdir = os.path.dirname(os.path.abspath(__file__))
        models = [f for f in os.listdir(fdir + os.sep + 'models') if f.startswith('Amidar')]
        print('num models:', len(models))
        for trained in models:
            print(trained)
            path = os.sep.join([fdir, 'models', trained])
            family = trained.split('.')[1]
            with tf.Session(graph=tf.Graph()):
                model = oai.getModel(self.env, family, seed, path)
                self.runTest(model)
        
class OneEnemyTargetTest(AmidarToyboxTestBase):

    def shouldIntervene(self):
        return self.tick == 0

    def onTrialEnd(self): pass

    def onTestEnd(self): pass

    def intervene(self):
      with ami.AmidarIntervention(self.getToybox()) as intervention:
        game = intervention.game
        game.jumps = 0
        game.lives = 1
        # intervene on a single enemy
        enemy = random.choice(game.enemies)
        start = ami.TilePoint(game.intervention, 0, 0)
        # Set the starting position to be the next one?
        start.pos = enemy.ai.next
        start_dir = ami.Direction(self, ami.Direction.directions[random.randint(0, 3)])
        vision_distance = max(game.board.height, game.board.width)
        dir = ami.Direction(self, ami.Direction.directions[random.randint(0, 3)])
        intervention.set_enemy_protocol(enemy, 'EnemyTargetPlayer', 
          start=start, 
          start_dir=start_dir,
          vision_distance=vision_distance,
          dir=dir,
          player_seen=None)
        self.trials = 2
        self.timeout = 1e5
        game.enemies = [enemy]
        assert self.dirty_state == True

    def test_scenario_ppo2(self):
      seed = 42
    #   fdir = os.path.dirname(os.path.abspath(__file__))
    #   path = os.sep.join([fdir, 'models', 'AmidarToyboxNoFrameskip-v4.ppo2.5e7.3771075072.2019-05-18.model'])
      path = '../models/AmidarToyboxNoFrameskip-v4.regress.model'
      model = oai.getModel(self.env, 'ppo2', seed, path)
      # Set low to be a test of a test!
      self.runTest(model)

class GangUpNoJumpRandomTest(AmidarToyboxTestBase):

    def shouldIntervene(self):
      return self.tick == 0

    def onTrialEnd(self): pass

    def onTestEnd(self): pass

    def intervene(self):
      with ami.AmidarIntervention(self.getToybox()) as intervention:
        game = intervention.game
        game.jumps = 0
        game.lives = 1
        num_enemies = len(game.enemies)

        sample_enemy = game.enemies[0] 
        game.enemies = []

        player_pos = game.player.position.to_tile_point()

        while num_enemies > 0:
          print('num_enemies:', num_enemies)
          num_enemies -= 1
          start = intervention.get_random_tile(lambda t: \
            # Should not be on top of another enemy, nor the player
            all([
                 abs(t.tx - player_pos.tx) > 2 and \
                 abs(t.ty - player_pos.ty) > 2 and \
                 abs(t.tx - e.position.to_tile_point().tx) > 2 and \
                 abs(t.ty - e.position.to_tile_point().ty) > 2
                     for e in game.enemies])
          ).to_tile_point()
          # Set the starting position to be close to the player's 
          # start position. I picked an arbitrary max distance (20)
          start_dir = ami.Direction.directions[random.randint(0, 3)]
          print('random start:', start, start_dir)
          dir = ami.Direction.directions[random.randint(0, 3)]

          # Create a copy.
          enemy = ami.Enemy.decode(intervention, sample_enemy.encode(), ami.Enemy)
          intervention.set_enemy_protocol(enemy, ami.MovementAI.EnemyRandomMvmt, 
            start=start, 
            start_dir=start_dir,
            dir=dir)
          game.enemies.append(enemy)

    def test_scenario_ppo2(self):
      seed = 42
      fdir = os.path.dirname(os.path.abspath(__file__))
      path = os.sep.join([fdir, 'models',  'AmidarToyboxNoFrameskip-v4.ppo2.5e7.3771075072.2019-05-18.model'])  
      model = oai.getModel(self.env, 'ppo2', seed, path)
      # Set low to be a test of a test!
      self.runTest(model)

class GangUpNoJumpTargetTest(AmidarToyboxTestBase):
  
    def shouldIntervene(self):
      return self.tick == 0

    def onTrialEnd(self):
      if hasattr(self, 'trialnum'):
        self.trialnum += 1
      else: self.trialnum = 1
      print('end trial %d', self.trialnum)
      with ami.AmidarIntervention(self.getToybox()) as ai:
        unpainted = len(ai.game.board.tiles.filter(ami.Tile.Unpainted))
        painted = len(ai.game.board.tiles.filter(ami.Tile.Painted))
        score = ai.game.score
        self.assertGreaterEqual(painted, 6)
        return {'painted': painted, 'unpainted': unpainted, 'score' : score}

    def onTestEnd(self):
      pass

    def intervene(self):
      with ami.AmidarIntervention(self.getToybox()) as intervention:
        game = intervention.game
        game.jumps = 0
        game.lives = 1
        for enemy in game.enemies:
          # We are expecting the default protocol to be enemy lookup
          assert enemy.ai.protocol == ami.MovementAI.EnemyLookupAI
          # Create an empty TilePoint
          start = ami.TilePoint(game.intervention, 0, 0)
          # Set the starting position to be close to the player's 
          # start position. I picked an arbitrary max distance (20)
          player_tile = game.player.position.to_tile_point()
          start.pos = intervention.get_random_tile(lambda t: \
              abs(t.tx - player_tile.tx) < 20 and \
              abs(t.ty - player_tile.ty) < 20)
          start_dir = ami.Direction.directions[random.randint(0, 3)]
          vision_distance = 5
          dir = ami.Direction.directions[random.randint(0, 3)]

          intervention.set_enemy_protocol(enemy, 'EnemyTargetPlayer',
            start=start, 
            start_dir=start_dir,
            vision_distance=vision_distance,
            dir=dir,
            player_seen=None)

    def test_scenario_ppo2(self):
      seed = 42
      fdir = os.path.dirname(os.path.abspath(__file__))
      path = os.sep.join([fdir, 'models',  'AmidarToyboxNoFrameskip-v4.ppo2.5e7.3771075072.2019-05-18.model'])  
      model = oai.getModel(self.env, 'ppo2', seed, path)
      # Set low to be a test of a test!
      self.runTest(model)