import unittest

class BehavioralFixture(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.setUpEnv()
    cls.setUpModel()

  @classmethod
  def setUpEnv(cls):
    pass

  @classmethod
  def setUpModel(cls):
    pass

  @classmethod
  def tearDownClass():
    tearDownEnv()
    tearDownModel()

  @classmethod
  def tearDownEnv(cls):
    pass

  def setUp(self, trials=30, timeout=5e6, record_period=10):
    self.obs = self.env.reset()
    self.trials = trials
    self.timeout = timeout
    self.record_period = record_period

  def log_after_episode(self):
    pass 

  def log_step(self):
    pass

  def takeAction(self):
    pass
