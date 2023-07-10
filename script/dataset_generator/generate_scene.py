import blenderproc as bproc
'''
Script to generate a synthetic dataset, stored in hdf5 format.
This dataset can contain:
 - RGB images
 - Object poses
 - Segmentation maps
 - Bounding boxes
 - Depth map
 - Normal map

To run, blenderproc and other things should be installed (virtual environment recommended):
$ conda activate dataset_generation
$ pip install blenderproc numpy
$ blenderproc quickstart # verify that it works, install minor dependencies


'''

import os
import numpy as np
import argparse
import json
from operator import itemgetter
from pathlib import Path
from typing import Callable, Dict, List, Tuple
import time

from blenderproc.python.types import MeshObjectUtility, EntityUtility


def bounding_box_2d_from_vertices(object: bproc.types.MeshObject, K: np.ndarray, camTworld: np.ndarray) -> Tuple[List[float], float, np.ndarray]:
  '''
  Compute the 2D bounding from an object's vertices
  returns A tuple containing:
    [xmin, ymin, xmax, ymax] in pixels 
    the proportion of visible vertices (that are not behind the camera, i.e., negative Z)
    The 2D points, in meters in camera space, in ViSP/OpenCV frame
  '''
  worldTobj = homogeneous_no_scaling(object)
  obj = object.blender_obj
  verts = np.ones(len(obj.data.vertices) * 3)
  obj.data.vertices.foreach_get("co", verts)
  points = verts.reshape(-1, 3)
  # verts = [v.co for v in obj.data.vertices]
  camTobj = camTworld @ worldTobj
  points_cam = camTobj @ np.concatenate((points, np.ones((len(points), 1))), axis=-1).T
  points_cam = convert_points_to_visp_frame((points_cam[:3] / points_cam[3, None]).T)
  
  visible_points = points_cam[points_cam[:, 2] > 0]
  visible_points_m_2d = visible_points[:, :2] / visible_points[:, 2, None]
  visible_points_px_2d = K @ np.concatenate((visible_points_m_2d, np.ones((len(visible_points_m_2d), 1))), axis=-1).T
  visible_points_px_2d = visible_points_px_2d.T[:, :2] / visible_points_px_2d.T[:, 2, None]
  
  mins = np.min(visible_points_px_2d, axis=0)
  assert len(mins) == 2
  maxes = np.max(visible_points_px_2d, axis=0)
  
  return [mins[0], mins[1], maxes[0], maxes[1]], len(visible_points) / len(points_cam), visible_points_m_2d

def homogeneous_inverse(aTb):
  bTa = aTb.copy()
  bTa[:3, :3] = bTa[:3, :3].T
  bTa[:3, 3] = -bTa[:3, :3] @ bTa[:3, 3]
  return bTa

def homogeneous_no_scaling(object: bproc.types.MeshObject):
  localTworld = np.eye(4)
  localTworld[:3, :3] = object.get_rotation_mat()
  localTworld[:3, 3] = object.get_location()
  return localTworld

def convert_to_visp_frame(aTb):
  '''
  Same as converting to an OpenCV frame
  '''
  return bproc.math.change_source_coordinate_frame_of_transformation_matrix(aTb, ["X", "-Y", "-Z"])

def convert_points_to_visp_frame(points: np.ndarray):
  points[:, 1:3] = -points[:, 1:3]
  return points

def point_in_bounding_box(object: bproc.types.MeshObject, bb_scale=1.0):
  '''
  Sample a random point in the bounding box of an object.
  the bounding box can be scaled with bb_scale if we wish to sample a point "near" the true bounding box
  Returned coordinates are in world frame
  '''

  bb = object.get_bound_box() * bb_scale # 8 x 3
  worldTlocal = homogeneous_no_scaling(object) # local2world includes scaling
  localTworld = homogeneous_inverse(worldTlocal)
  # go to object space to sample with axis aligned bb, since sampling in world space would be harder
  bb_local = localTworld @ np.concatenate((bb, np.ones((8, 1))), axis=-1).T
  bb_local = bb_local.T[:, :3] # 8 X 3
  mins, maxes = np.min(bb_local, axis=0), np.max(bb_local, axis=0)
  point_local = np.zeros(3)
  for i in range(3):
    point_local[i] = np.random.uniform(mins[i], maxes[i])
  point = worldTlocal @ np.concatenate((point_local, np.ones(1)))[:, None]
  point = point[:3, 0]
  return point

def object_bb_length(object: bproc.types.MeshObject) -> float:
  size = 0.0
  bb = object.get_bound_box()
  for corner_index in range(len(bb) - 1):
    dists = np.linalg.norm(bb[corner_index+1:] - bb[corner_index], axis=-1, ord=2)
    size = max(np.max(dists), size)
  return size

def randomize_pbr(objects: List[bproc.types.MeshObject], noise):
  # set shading and physics properties and randomize PBR materials
  for j, obj in enumerate(objects):
      rand_angle = np.random.uniform(30, 90)
      obj.set_shading_mode('auto', rand_angle)
      mat = obj.get_materials()[0]
      keys = ["Roughness", "Specular", "Metallic"]
      for k in keys:
        base_value = mat.get_principled_shader_value(k)
        new_value = None
        import bpy
        if isinstance(base_value, bpy.types.NodeSocketColor):
          new_value = base_value.default_value + np.concatenate((np.random.uniform(-noise, noise, size=3), [1.0]))
          #base_value.default_value = new_value
          new_value = base_value
        elif isinstance(base_value, float):
          new_value = max(0.0, min(1.0, base_value + np.random.uniform(-noise, noise)))
        if new_value is not None:
          mat.set_principled_shader_value(k, new_value)

def add_displacement(objects: List[bproc.types.MeshObject], max_displacement_strength=0.05):
  for obj in objects:
    obj.add_uv_mapping("cylinder")

    # Create a random procedural texture
    noise_models = ["CLOUDS", "DISTORTED_NOISE", "MAGIC", "MARBLE",
                     "MUSGRAVE", "NOISE", "STUCCI", "VORONOI", "WOOD"]
    texture = bproc.material.create_procedural_texture(noise_models[np.random.choice(len(noise_models))])
    # Displace the vertices of the object based on that random texture
    obj.add_displace_modifier(
        texture=texture,
        strength=np.random.uniform(0, max_displacement_strength),
        subdiv_level=1,
    )


class Scene:
  def __init__(self, size: float, target_objects: List[bproc.types.MeshObject],
               distractors: List[bproc.types.MeshObject], room_objects: List[bproc.types.MeshObject], lights: List[bproc.types.MeshObject]):
    self.size = size
    self.target_objects = target_objects
    self.distractors = distractors
    self.room_objects = room_objects
    self.lights = lights

  def cleanup(self):
    objects = self.target_objects + self.distractors + self.room_objects
    for object in objects:
      object.delete(True)
    for light in self.lights:
      light.delete(True)

class Generator:
  def __init__(self, config_path: Path, scene_index: int, scene_count: int):
    self.config_path = config_path
    with open(self.config_path, 'r') as json_config_file:
      self.json_config = json.load(json_config_file)
    print(self.json_config)
    np.random.seed(self.json_config['numpy_seed'] * (scene_index + 1))
    self.scene_index = scene_index
    self.scene_count = scene_count
    blender_seed_int = int(self.json_config['blenderproc_seed'])
    os.environ['BLENDER_PROC_RANDOM_SEED'] = str(blender_seed_int * (scene_index + 1))
    self.objects = None
    self.classes = None
    


  def init(self):
    print('Loading objects...')
    if self.objects is not None:
      for k in self.objects:
        self.objects[k].delete()
    self.objects, self.classes = self.load_objects()
    self.save_class_file()
    print('Preloading CC0 textures...')
    self.cc_textures = bproc.loader.load_ccmaterials(self.json_config['cc_textures_path'], preload=True)
    self.cc_textures = np.random.choice(self.cc_textures, size=self.json_config['scene']['max_num_textures'])
    self.setup_renderer()

  def load_objects(self) -> Dict[str, bproc.types.MeshObject]:
    '''
    Load the objects in the models directory
    The directory should have the following structure:
    - models/
    --- obj_1_name/
    ----- model.obj
    --- obj_2_name/
    ----- model.obj
    Returns a dict where keys are the model names
    (from the containing folder name of each object,
    in the example case: 'obj_1_name' and 'obj_2_name')
    and the values are the loaded model
    '''
    models_dict = {}
    class_dict = {}
    models_path = Path(self.json_config['models_path']).absolute()
    cls = 1
    assert models_path.exists() and models_path.is_dir(), f'Models path {models_path} must exist and be a directory'
    for model_dir in sorted(models_path.iterdir()):
      if not model_dir.is_dir():
        continue
      model_name = model_dir.name
      for content in sorted(model_dir.iterdir()):
        if not content.is_file():
          continue
        load_fn: Callable[[str], List[bproc.types.MeshObject]] = None
        if content.name.endswith('.obj') or content.name.endswith('.ply'):
          load_fn = bproc.loader.load_obj
        if load_fn is not None:
          assert model_name not in models_dict, f'A folder should contain a single object, but {content} contains multiple objects (.blend or .obj)'
          models = load_fn(str(content.absolute()))
          assert len(models) > 0, f'Loaded an empty file: {content}'
          model = models[0]
          if len(models) > 1:
            model.join_with_other_objects(models[1:])
          model.set_cp('category_id', cls)
          model.set_location([-1000.0, -1000.0, -1000.0]) # Avoid warning about collisions with other objects in the scene
          model.hide() # Hide by default
          model.set_name(model_name)
          models_dict[model_name] = model
          class_dict[model_name] = cls
          cls += 1
    return models_dict, class_dict
  def save_class_file(self):
    save_path = Path(self.json_config['dataset']['save_path']).absolute()
    cls_file = save_path / 'classes.txt'
    if self.scene_index == 0 or not cls_file.exists():
      with open(cls_file, 'w') as f:
        cls_to_model_name = {self.classes[k]: k for k in self.classes.keys()}
        cls_indices = sorted(cls_to_model_name.keys())
        lines = []
        for i in cls_indices:
          lines.append(cls_to_model_name[i])
        print(f'Writing classes to file: \n {lines}')
        f.writelines(lines)
  def setup_renderer(self):
    depth = itemgetter('depth')(self.json_config['dataset'])
    bproc.renderer.set_max_amount_of_samples(self.json_config['rendering']['max_num_samples'])
    if depth:
      bproc.renderer.enable_depth_output(activate_antialiasing=False)
    # if normals:
    #   bproc.renderer.enable_normals_output()

  def render(self) -> Dict:
    '''

    '''
    normals, segmentation = itemgetter('normals', 'segmentation')(self.json_config['dataset'])
    if normals: # Ugly, but doesn't work if it isn't called every render
      bproc.renderer.enable_normals_output()
    data = bproc.renderer.render()

    if segmentation:
      data.update(bproc.renderer.render_segmap(map_by=["instance", "class"]))
    return data

  def save_data(self, path: Path, objects: List[bproc.types.MeshObject], data: Dict):
    json_dataset = self.json_config['dataset']

    out_object_pose, out_bounding_box = itemgetter('pose', 'detection')(json_dataset)
    keys = [
      'min_side_size_px', 'min_visibility_percentage',
      'points_sampling_occlusion'
    ]
    min_side_px, min_visibility, points_sampling_occlusion = itemgetter(*keys)(json_dataset['detection_params'])
    
    width, height = itemgetter('w', 'h')(self.json_config['camera'])
    frames_data = []
    import time
    for frame in range(bproc.utility.num_frames()):
      
      worldTcam = bproc.camera.get_camera_pose(frame)
      camTworld = homogeneous_inverse(worldTcam)
      K = bproc.camera.get_intrinsics_as_K_matrix()
      
      minx, miny = (-K[0, 2]) / K[0, 0], (-K[1, 2]) / K[1, 1]
      maxx, maxy = (width -K[0, 2]) / K[0, 0], (height -K[1, 2]) / K[1, 1]

      visible_objects = bproc.camera.visible_objects(worldTcam, min(width, height) // min_side_px)
      objects_data = []
      for object in objects:
        if object not in visible_objects:
          continue
        object_data = {
          'class': object.get_cp('category_id', frame),
          'name': object.get_name()
        }
        if out_object_pose:
          worldTobj = homogeneous_no_scaling(object)
          camTobj = camTworld @ worldTobj
          object_data['cTo'] = convert_to_visp_frame(camTobj)
        if out_bounding_box:
          t = time.time()
          bb_corners, z_front_proportion, points_im = bounding_box_2d_from_vertices(object, K, camTworld)
          if z_front_proportion < min_visibility:
            continue
          mins = np.array([bb_corners[0], bb_corners[1]])
          maxes = np.array([bb_corners[2], bb_corners[3]])

          original_size = maxes - mins
          original_area = np.prod(original_size)
          mins = np.maximum(mins, [0, 0])
          maxes = np.minimum(maxes, [width, height])
          size = maxes - mins
          area = np.prod(size)

          # Filter objects that are too small to be believably detectable
          if size[0] < min_side_px or size[1] < min_side_px:
            continue

          
          vis_points_in_image = points_im[(points_im[:, 0] > minx) & ((points_im[:, 0] < maxx)) & (points_im[:, 1] > miny) & ((points_im[:, 1] < maxy))]

          base_visibility = z_front_proportion * (len(vis_points_in_image) / len(points_im))
          # Camera clipping removes too much of the object
          if base_visibility < min_visibility:
            continue
          if points_sampling_occlusion > 0:
            point_count = len(vis_points_in_image)
            points = vis_points_in_image[np.random.choice(point_count, size=min(point_count, points_sampling_occlusion))]
            points = np.concatenate((points, np.ones((len(points), 1))), axis=-1)
            
            points_cam = convert_points_to_visp_frame(points) # Convert back to blender frame
            points_world = worldTcam @ np.concatenate((points_cam, np.ones((len(points_cam), 1))), axis=-1).T
            points_world = (points_world[:3] / points_world[3, None]).T
            ray_directions = points_world - worldTcam[None, :3, 3]
            hit_count = 0
            for ray in ray_directions:
              hit_object = bproc.object.scene_ray_cast(worldTcam[:3, 3], ray)[-2]
              if hit_object == object:
                hit_count += 1

            final_visibility = base_visibility * (hit_count / len(ray_directions))
            print(final_visibility)
            # Including occlusions, the object is now not visible enough to be detectable
            if final_visibility < min_visibility:
              print(f'Filtered object {object.get_name()}, because of occlusions: {final_visibility}')
              continue
          object_data['bounding_box'] = [mins[0], mins[1], size[0], size[1]]


        objects_data.append(object_data)
      frames_data.append(objects_data)
    data['object_data'] = frames_data
    bproc.writer.write_hdf5(str(path.absolute()), data, append_to_existing_output=False)



  def set_camera_intrinsics(self) -> None:
    '''
    Set camera intrinsics from config.
    Randomized depending on randomize_params_percent. This does not impact image resolution
    '''
    px, py, u0, v0, h, w , r = itemgetter('px', 'py', 'u0', 'v0', 'h', 'w', 'randomize_params_percent')(self.json_config['camera'])
    r = r / 100.0
    randomize = lambda x: x + np.random.uniform(-x * r, x * r)
    K = [
      [randomize(px), 0, randomize(u0)],
      [0, randomize(py), randomize(v0)],
      [0, 0, 1],
    ]
    bproc.camera.set_intrinsics_from_K_matrix(K, w, h)


  def create_distractors(self, scene_size, other_objects) -> List[bproc.types.MeshObject]:
    json_distractors = self.json_config['scene']['distractors']
    min_count, max_count = itemgetter('min_count', 'max_count')(json_distractors)
    min_size, max_size = itemgetter('min_size_rel_scene', 'max_size_rel_scene')(json_distractors)
    displacement_strength, pbr_noise = itemgetter('displacement_max_amount', 'pbr_noise')(json_distractors)

    count = np.random.randint(min_count, max_count + 1)
    if count == 0:
      return []
    def sample_pose(obj: bproc.types.MeshObject):
      loc = np.random.uniform([-scene_size / 2, -scene_size / 2, -scene_size / 2], [scene_size / 2, scene_size / 2, scene_size / 2])
      obj.set_location(loc)
      obj.set_scale(np.random.uniform(scene_size * min_size, scene_size * max_size, size=3))
      obj.set_rotation_euler(bproc.sampler.uniformSO3())
    distractor_type = np.random.choice(['CUBE', 'CYLINDER', 'CONE', 'SPHERE', 'MONKEY'], size=count, replace=True)
    distractors = [bproc.object.create_primitive(distractor_type[c]) for c in range(count)]

    bproc.object.sample_poses(
      distractors,
      sample_pose_func=sample_pose,
      objects_to_check_collisions=None
    )

    for obj in distractors:
      random_texture = np.random.choice(self.cc_textures)
      obj.replace_materials(random_texture)
    randomize_pbr(distractors, pbr_noise)
    if displacement_strength > 0.0:
      add_displacement(distractors, displacement_strength)
    return distractors

  def create_lights(self, scene_size, target_objects) -> List[bproc.types.Light]:
    light_json = self.json_config['scene']['lights']
    min_count, max_count = itemgetter('min_count', 'max_count')(light_json)
    min_intensity, max_intensity = itemgetter('min_intensity', 'max_intensity')(light_json)

    count = np.random.randint(min_count, max_count + 1)
    point_light_count = np.sum(np.random.choice(2, size=count, replace=True))
    spot_light_count = count - point_light_count

    lights = []
    def basic_light_sampling(light: bproc.types.Light) -> None:
      loc = np.random.uniform([-scene_size / 2, -scene_size / 2, -scene_size / 2], [scene_size / 2, scene_size / 2, scene_size / 2])
      light.set_location(loc)
      light.set_energy(np.random.uniform(min_intensity, max_intensity))
      light.set_color(np.random.uniform(0.5, 1.0, size=3))

    for _ in range(point_light_count):
      light = bproc.types.Light('POINT')
      basic_light_sampling(light)
      lights.append(light)
    for _ in range(spot_light_count):
      light = bproc.types.Light('SPOT')
      basic_light_sampling(light)
      looked_at_obj = np.random.choice(len(target_objects))
      looked_at_obj: bproc.types.MeshObject = target_objects[looked_at_obj]
      poi = point_in_bounding_box(looked_at_obj)
      R = bproc.camera.rotation_from_forward_vec(poi - light.get_location())
      light.set_rotation_mat(R)
      lights.append(light)

    return lights

  def create_target_objects(self) -> List[bproc.types.MeshObject]:
    json_objects = self.json_config['scene']['objects']
    min_count, max_count, replace = itemgetter('min_count', 'max_count', 'multiple_occurences')(json_objects)
    scale_noise, displacement_amount, pbr_noise = itemgetter('scale_noise', 'displacement_max_amount', 'pbr_noise')(json_objects)

    object_keys = list(self.objects.keys())

    if not replace:
      max_count = min(max_count, len(object_keys))
    count = np.random.randint(min_count, max_count + 1)
    selected_key_indices = np.random.choice(len(object_keys), size=count, replace=replace)

    objects: List[bproc.types.MeshObject] = [self.objects[object_keys[index]].duplicate() for index in selected_key_indices]
    for object in objects:
      object.hide(False)
      if scale_noise > 0.0:
        random_scale = np.random.uniform(-scale_noise, scale_noise) + 1.0
        object.set_scale([random_scale, random_scale, random_scale]) # Uniform scaling
      object.set_location([0.0, 0.0, 0.0])
      object.persist_transformation_into_mesh()

    if displacement_amount > 0.0:
      add_displacement(objects, displacement_amount)
    if pbr_noise > 0.0:
      randomize_pbr(objects, pbr_noise)

    return objects

  def create_room(self, size: float) -> List[bproc.types.MeshObject]:
    ground = bproc.object.create_primitive('PLANE')
    ground.set_location([0, 0, -size / 2])
    ground.set_scale([size / 2, size / 2, 1])
    room_objects = [ground]
    wall_data = [
      {'loc': [size / 2, 0, 0], 'rot': [0, np.pi / 2, 0]},
      {'loc': [-size / 2, 0, 0], 'rot': [0, np.pi / 2, 0]},
      {'loc': [0, size / 2, 0], 'rot': [np.pi / 2, 0, 0]},
      {'loc': [0, -size / 2, 0], 'rot': [np.pi / 2, 0, 0]},
      {'loc': [0, 0, size / 2], 'rot': [0.0, 0, 0]},
    ]
    for w_data in wall_data:
      wall = bproc.object.create_primitive('PLANE')
      wall.set_location(w_data['loc'])
      wall.set_rotation_euler(w_data['rot'])
      wall.set_scale([size / 2, size / 2, 1])
      room_objects.append(wall)

    for obj in room_objects:
      random_texture = np.random.choice(self.cc_textures)
      obj.replace_materials(random_texture)
    randomize_pbr(room_objects, 0.2)
    return room_objects

  def create_scene(self):
    '''
    Create a basic scene, a square room.
    The size of the room is dependent on the size of the biggest object multiplied by a user supplied param
    Each wall has a random texture, sampled from cc0 materials
    Distractors are added randomly in the room
    Random lights are also placed
    '''

    room_size = 0.0
    room_size_multiplier_min, room_size_multiplier_max = itemgetter('room_size_multiplier_min', 'room_size_multiplier_max')(self.json_config['scene'])
    simulate_physics = self.json_config['scene']['simulate_physics']

    assert room_size_multiplier_min >= 1.0, 'Room size multiplier should be more than one'
    objects = self.create_target_objects()

    for object in objects:
        room_size = max(object_bb_length(object), room_size)
    size = room_size * np.random.uniform(room_size_multiplier_min, room_size_multiplier_max)

    room_objects = self.create_room(size)

    def sample_pose(obj: bproc.types.MeshObject):
      loc = np.random.uniform([-size / 2, -size / 2, -size / 2], [size / 2, size / 2, size / 2])
      obj.set_location(loc)
      obj.set_rotation_euler(bproc.sampler.uniformSO3())

    bproc.object.sample_poses(
      objects,
      sample_pose_func=sample_pose,
      objects_to_check_collisions=None
    )

    for object in objects:
      object.persist_transformation_into_mesh()

    distractors = self.create_distractors(size, room_objects + objects)


    if simulate_physics:
      for object in objects + distractors:
        object.enable_rigidbody(True)
      for object in room_objects:
        object.enable_rigidbody(False, collision_shape='BOX')

      bproc.object.simulate_physics_and_fix_final_poses(min_simulation_time=3, max_simulation_time=3.5, check_object_interval=1)
    for object in objects:
      object.persist_transformation_into_mesh()
    def filter_objects_outside_room(objects: List[bproc.types.MeshObject]) -> List[bproc.types.MeshObject]:
      inside = []
      outside = []
      is_inside = lambda loc: np.all(np.logical_and(loc < size / 2, loc > -size / 2))
      for object in objects:
        inside.append(object) if is_inside(object.get_location()) else outside.append(object)
      for object in outside:
        object.delete()

      print(f'Filtered {len(objects) - len(inside)} objects')
      return inside

    objects = filter_objects_outside_room(objects)
    distractors = filter_objects_outside_room(distractors)
    lights = self.create_lights(size, objects)

    return Scene(size, objects, distractors, room_objects, lights)

  def sample_camera_poses(self, scene: Scene) -> None:
    dataset_config = self.json_config['dataset']
    images_per_scene = dataset_config['images_per_scene']
    cam_min_dist, cam_max_dist = itemgetter('cam_min_dist_rel', 'cam_max_dist_rel')(self.json_config['scene']['objects'])
    hs = scene.size / 2
    bvh = bproc.object.create_bvh_tree_multi_objects(scene.target_objects + scene.distractors + scene.room_objects)
    for frame in range(images_per_scene):
      tries = 0
      good = False
      while not good and tries < 1000:
        object = scene.target_objects[np.random.choice(len(scene.target_objects))]
        object_size = object_bb_length(object)
        poi = point_in_bounding_box(object, bb_scale=1)
        tries_distance = 0
        distance = np.random.uniform(cam_min_dist, cam_max_dist)
        while not good and tries_distance < 100:
          location = bproc.sampler.sphere(object.get_location(), distance * object_size, 'SURFACE')
          rotation_matrix = bproc.camera.rotation_from_forward_vec(poi - location, inplane_rot=np.random.uniform(-0.7854, 0.7854))
          import bpy
          cam = bpy.context.scene.camera.data
          clip_start = cam.clip_start
          focal_length = cam.lens / 1000.0

          cam2world_matrix = bproc.math.build_transformation_mat(location, rotation_matrix)
          if object in bproc.camera.visible_objects(cam2world_matrix, 20) and bproc.camera.perform_obstacle_in_view_check(cam2world_matrix, {'min': focal_length + clip_start}, bvh):
            good = True
          else:
            good = False
          tries += 1
          tries_distance += 1
      if tries >= 1000:
        print('Warning! Could not correctly place camera, results may be wrong')
      bproc.camera.add_camera_pose(cam2world_matrix)

  def run(self):
    save_path = Path(self.json_config['dataset']['save_path'])
    save_path.mkdir(exist_ok=True)
    self.init()
    import bpy
    for i in range(self.scene_count):
      bproc.utility.reset_keyframes()
      self.set_camera_intrinsics()
      scene = self.create_scene()
      bproc.loader.load_ccmaterials(self.json_config['cc_textures_path'], fill_used_empty_materials=True)
      self.sample_camera_poses(scene)
      bpy.context.scene.render.use_persistent_data = True
      data = self.render()
      path = save_path / str(self.scene_index + i)
      path.mkdir(exist_ok=True)
      self.save_data(path, scene.target_objects, data)
      scene.cleanup()

      




from blenderproc.python.renderer import RendererUtility

if __name__ == '__main__':

  parser = argparse.ArgumentParser()
  parser.add_argument('--config', required=True, type=str, help='Path to the JSON configuration file for the dataset generation script')
  parser.add_argument('--scene-index', required=True, type=int, help='Index of the first scene to generate')
  parser.add_argument('--scene-count', required=True, type=int, help='Number of scenes to render')
  args = parser.parse_args()

  generator = Generator(args.config, args.scene_index, args.scene_count)
  # RendererUtility.set_render_devices(use_only_cpu=True)
  bproc.clean_up(clean_up_camera=True)
  bproc.init() # Works if you have a GPU
  generator.run()


