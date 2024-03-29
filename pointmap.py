import numpy as np
import OpenGL.GL as gl
import pangolin
import g2o

from multiprocessing import Process, Queue

class Point(object):
  # A Point is a 3-D point in the world
  # Each Point is observed in multiple Frames

  def __init__(self, mapp, loc):
    #pt is position
    self.pt = loc
    #frame object
    self.frames = []
    #idxs ID of the point
    self.idxs = []
    
    #make the length as the id
    self.id = len(mapp.points)
    #make the map object add the point
    mapp.points.append(self)

  def add_observation(self, frame, idx):
    #the frame and its id
    frame.pts[idx] = self
    self.frames.append(frame)
    self.idxs.append(idx)



class Map(object):
  def __init__(self):
    # the Map has frames, points, state and a queue
    self.frames = []
    self.points = []
    self.state = None
    self.q = Queue()

    #multiprocessing the function viewer_thread()
    p = Process(target=self.viewer_thread, args=(self.q,))
    p.daemon = True
    p.start()
    
    
    
  # *** optimizer ***

  def optimize(self):
    # create g2o optimizer
    opt = g2o.SparseOptimizer()
    solver = g2o.BlockSolverSE3(g2o.LinearSolverCholmodSE3())
    solver = g2o.OptimizationAlgorithmLevenberg(solver)
    opt.set_algorithm(solver)
    
    robust_kernel = g2o.RobustKernelHuber(np.sqrt(5.991))
    
    # add frames(pose) to graph
    for f in self.frames:
      sbacam = g2o.SBACam(g2o.SE3Quat(f.pose[0:3, 0:3], f.pose[0:3, 3]))
      sbacam.set_cam(f.K[0][0], f.K[1][1], f.K[2][0], f.K[2][1], 1.0)
      
      v_se3 = g2o.VertexCam()
      v_se3.set_id(f.id)
      v_se3.set_estimate(sbacam)
      v_se3.set_fixed(f.id == 0)
      opt.add_vertex(v_se3)
      
    # add points to frames(pose)
    for p in self.points:
      pt = g2o.VertexSBAPointXYZ()
      pt.set_id(p.id + 0x10000)
      pt.set_estimate(p.pt[0:3])    
      pt.set_marginalized(True)    
      pt.set_fixed(False)
      opt.add_vertex(pt)      
      
      for f in p.frames:      
        edge = g2o.EdgeProjectP2MC()      
        edge.set_vertex(0, pt)     
        edge.set_vertex(1, opt.vertex(f.id)) 
        uv = f.kps[f.pts.index(p)]
        edge.set_measurement(uv)        
        edge.set_information(np.eye(2))        
        edge.set_robust_kernel(robust_kernel)        
        opt.add_edge(edge)
        
    opt.set_verbose(True)
    opt.initialize_optimization()
    opt.optimize(20)        
        


  def viewer_thread(self, q):
    self.viewer_init(1024, 768)
    while 1:
      self.viewer_refresh(q)

  def viewer_init(self, w, h):
    pangolin.CreateWindowAndBind('Main', w, h)
    gl.glEnable(gl.GL_DEPTH_TEST)

    self.scam = pangolin.OpenGlRenderState(
      pangolin.ProjectionMatrix(w, h, 420, 420, w//2, h//2, 0.2, 1000),
      pangolin.ModelViewLookAt(0, -10, -8,
                               0, 0, 0,
                               0, -1, 0))
    self.handler = pangolin.Handler3D(self.scam)

    # Create Interactive View in window
    self.dcam = pangolin.CreateDisplay()
    self.dcam.SetBounds(0.0, 1.0, 0.0, 1.0, -w/h)
    self.dcam.SetHandler(self.handler)

  def viewer_refresh(self, q):
    if self.state is None or not q.empty():
      self.state = q.get()

    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gl.glClearColor(1.0, 1.0, 1.0, 1.0)
    self.dcam.Activate(self.scam)

    # draw poses
    gl.glColor3f(0.0, 1.0, 0.0)
    pangolin.DrawCameras(self.state[0])

    # draw keypoints
    gl.glPointSize(2)
    gl.glColor3f(1.0, 0.0, 0.0)
    pangolin.DrawPoints(self.state[1])

    pangolin.FinishFrame()

  def display(self):
    poses, pts = [], []
    for f in self.frames:
      poses.append(f.pose)
    for p in self.points:
      pts.append(p.pt)
    self.q.put((np.array(poses), np.array(pts)))

