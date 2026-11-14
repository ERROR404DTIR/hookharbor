import tempfile, unittest
from pathlib import Path
import app
class HookTests(unittest.TestCase):
 def test_round_trip(self):
  with tempfile.TemporaryDirectory() as d:
   db=str(Path(d)/"x.db")
   i=app.save_event(db,"POST","/hook",{"X-Test":"yes"},b'{"x":1}',"application/json","127.0.0.1")
   self.assertEqual(i,1);self.assertEqual(app.event_list(db)[0]["method"],"POST")
   self.assertEqual(app.event_detail(db,i)["body_text"],'{"x":1}')
if __name__=="__main__":unittest.main()
