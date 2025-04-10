from pathlib import Path
import urllib.request

import pytest
import numpy as np

from test import config

from pymoab import core

import pydagmc

# same as the DAGMC model used in the OpenMC DAGMC "legacy" test
FUEL_PIN_URL = 'https://tinyurl.com/y3ugwz6w' # 1.2 MB


def download(url, filename="pydagmc.h5m"):
    """
    Helper function for retrieving dagmc models
    """
    u = urllib.request.urlopen(url)

    if u.status != 200:
        raise RuntimeError("Failed to download file.")

    # save file via bytestream
    with open(filename, 'wb') as f:
        f.write(u.read())


@pytest.fixture(autouse=True, scope='module')
def fuel_pin_model(request):
    fuel_pin_path = request.path.parent / "fuel_pin.h5m"
    if not Path(fuel_pin_path).exists():
        download(FUEL_PIN_URL, fuel_pin_path)
    return str(fuel_pin_path)


def test_model_repr(fuel_pin_model):
    model = pydagmc.DAGModel(fuel_pin_model)
    model_str = repr(model)
    assert model_str == 'DAGModel: 4 Volumes, 21 Surfaces, 5 Groups'

def test_basic_functionality(request, capfd):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    groups = model.groups_by_name
    print(groups)
    # ensure that the groups attribude is indexable
    first_group = model.groups[0]
    assert isinstance(first_group, pydagmc.Group)

    fuel_group = groups['mat:fuel']
    print(fuel_group)

    v1 = fuel_group.volumes_by_id[1]
    print(v1)

    groups['mat:fuel'].remove_set(v1)
    groups['mat:41'].add_set(v1)

    print(groups['mat:fuel'])
    print(groups['mat:41'])

    assert fuel_group.name == 'mat:fuel'
    fuel_group.name = 'kalamazoo'
    assert fuel_group.name == 'kalamazoo'

    print(fuel_group.name)

    #####################################
    # All test code must go before here #
    #####################################
    out, err = capfd.readouterr()

    gold_name = request.path.parent / 'gold_files' / f'.{request.node.name}.gold'
    if config['update']:
        f = open(gold_name, 'w')
        f.write(out)
    else:
        f = open(gold_name, 'r')
        assert out == f.read()


def test_group_merge(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    groups = model.groups_by_name

    orig_group = groups['mat:fuel']
    orig_group_size = len(orig_group.volumes)
    # try to create a new group with the same name as another group
    new_group = pydagmc.Group.create(model, 'mat:fuel')
    assert orig_group == new_group

    # check that we can update a set ID
    new_group.id = 100
    assert new_group.id == 100

    # merge the new group into the existing group
    orig_group.merge(new_group)
    assert orig_group == new_group

    # re-add a new group to the instance with the same name
    new_group = pydagmc.Group.create(model, 'mat:fuel')

    # add one of other volumes to the new set
    for vol in model.volumes:
        new_group.add_set(vol)

    # using create_group should give same thing
    assert model.create_group('mat:fuel') == new_group

    assert orig_group == new_group
    assert len((new_group.volume_ids)) == len(model.volumes)

    # now get the groups again
    groups = model.groups_by_name
    # the group named 'mat:fuel' should contain the additional
    # volume set w/ ID 3 now
    fuel_group = groups['mat:fuel']
    assert 3 in fuel_group.volumes_by_id


def test_group_create(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    orig_num_groups = len(model.groups)

    # Create two new groups
    new_group1 = pydagmc.Group.create(model, 'mat:slime')
    new_group2 = model.create_group('mat:plastic')

    assert 'mat:slime' in model.groups_by_name
    assert 'mat:plastic' in model.groups_by_name
    assert model.groups_by_name['mat:slime'] == new_group1
    assert model.groups_by_name['mat:plastic'] == new_group2
    assert len(model.groups) == orig_num_groups + 2


def test_volume(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)

    v1 = model.volumes_by_id[1]
    assert v1.material == 'fuel'
    assert v1 in model.groups_by_name['mat:fuel']

    v1.material = 'olive oil'
    assert v1.material == 'olive oil'
    assert 'mat:olive oil' in model.groups_by_name
    assert v1 in model.groups_by_name['mat:olive oil']
    assert v1 not in model.groups_by_name['mat:fuel']

    new_vol = pydagmc.Volume.create(model, 100)
    assert isinstance(new_vol, pydagmc.Volume)
    assert new_vol.id == 100
    assert model.volumes_by_id[100] == new_vol

    new_vol2 = model.create_volume(200)
    assert isinstance(new_vol2, pydagmc.Volume)
    assert new_vol2.id == 200
    assert model.volumes_by_id[200] == new_vol2

def test_surface(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)

    s1 = model.surfaces_by_id[1]
    assert s1.volumes == [model.volumes_by_id[1], model.volumes_by_id[2]]
    assert s1.forward_volume == model.volumes_by_id[1]
    assert s1.reverse_volume == model.volumes_by_id[2]

    s1.forward_volume = model.volumes_by_id[3]
    assert s1.forward_volume == model.volumes_by_id[3]
    assert s1.surf_sense == [model.volumes_by_id[3], model.volumes_by_id[2]]

    s1.reverse_volume = model.volumes_by_id[1]
    assert s1.reverse_volume == model.volumes_by_id[1]
    assert s1.surf_sense == [model.volumes_by_id[3], model.volumes_by_id[1]]

def test_id_safety(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)

    v1 = model.volumes_by_id[1]

    used_vol_id = 2
    with pytest.raises(ValueError, match="already"):
        v1.id = used_vol_id

    # set volume 1 to a safe ID and ensure assignment was successful this
    # assignment should free the original ID of 1 for use
    safe_vol_id = 9876
    v1.id = safe_vol_id
    assert v1.id == safe_vol_id

    # create a second volume and ensure it gets the next available ID
    v2 = pydagmc.Volume.create(model)
    assert v2.id == safe_vol_id + 1

    # update the value of the first volume, freeing the ID
    safe_vol_id = 101
    v1.id = safe_vol_id
    # delete the second volume, freeing its ID as well
    v2.delete()

    # create a new volume and ensure that it is automatically assigned the
    # lowest available ID
    v3 = pydagmc.Volume.create(model)
    assert v3.id == safe_vol_id + 1

    s1 = model.surfaces_by_id[1]

    used_surf_id = 2
    with pytest.raises(ValueError, match="already"):
        s1.id = used_surf_id

    safe_surf_id = 9876
    s1.id = safe_surf_id
    assert s1.id == safe_surf_id

    s2 = model.surfaces_by_id[2]
    s2.id = None
    assert s2.id == safe_surf_id + 1

    s2.id = 2
    assert s2.id == 2

    g1 = model.groups_by_name['mat:fuel']

    used_grp_id = 2
    with pytest.raises(ValueError, match="already"):
        g1.id = used_grp_id

    safe_grp_id = 9876
    g1.id = safe_grp_id
    assert g1.id == safe_grp_id


    new_surf = pydagmc.Surface.create(model, 100)
    assert isinstance(new_surf, pydagmc.Surface)
    assert new_surf.id == 100
    assert model.surfaces_by_id[100] == new_surf

    new_surf2 = model.create_surface(200)
    assert isinstance(new_surf2, pydagmc.Surface)
    assert new_surf2.id == 200
    assert model.surfaces_by_id[200] == new_surf2


def test_hash(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)

    d = {group: group.name for group in model.groups}

    # check that an entry for the same volume with a different model can be entered
    # into the dict
    model1 = pydagmc.DAGModel(test_file)

    d.update({group: group.name for group in model1.groups})

    assert len(d) == len(model.groups) + len(model1.groups)

def test_compressed_coords(request, capfd):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    groups = pydagmc.DAGModel(test_file).groups_by_name

    fuel_group = groups['mat:fuel']
    v1 = fuel_group.volumes_by_id[1]

    conn, coords = v1.get_triangle_conn_and_coords()
    uconn, ucoords = v1.get_triangle_conn_and_coords(compress=True)

    for i in range(v1.num_triangles):
        assert (coords[conn[i]] == ucoords[uconn[i]]).all()

    conn_map, coords = v1.get_triangle_coordinate_mapping()
    tris = v1.triangle_handles
    assert (conn_map[tris[0]].size == 3)
    assert (coords[conn_map[tris[0]]].size == 9)


def test_coords(request, capfd):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    groups = model.groups_by_name

    group = groups['mat:fuel']
    conn, coords = group.get_triangle_conn_and_coords()

    volume = next(iter(group.volumes))
    conn, coords = volume.get_triangle_conn_and_coords(compress=True)

    surface = next(iter(volume.surfaces))
    conn, coords = surface.get_triangle_conn_and_coords(compress=True)


def test_to_vtk(tmpdir_factory, request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    groups = pydagmc.DAGModel(test_file).groups_by_name

    fuel_group = groups['mat:fuel']

    vtk_filename = str(tmpdir_factory.mktemp('vtk').join('fuel_pin.vtk'))

    fuel_group.to_vtk(vtk_filename)

    vtk_file = open(vtk_filename, 'r')

    gold_name = request.path.parent / 'gold_files' / f'.{request.node.name}.gold'

    if config['update']:
        f = open(gold_name, 'w')
        f.write(vtk_file.read())
    else:
        gold_file = open(gold_name, 'r')

        # The VTK file header has a MOAB version in it. Filter
        # that line out so running this test with other versions of
        # MOAB doesn't cause a failure
        line_filter = lambda line : not 'MOAB' in line

        vtk_iter = filter(line_filter, vtk_file)
        gold_iter = filter(line_filter, gold_file)
        assert all(l1 == l2 for l1, l2 in zip(vtk_iter, gold_iter))


@pytest.mark.parametrize("category,dim", [('Surface', 2), ('Volume', 3), ('Group', 4)])
def test_empty_category(category, dim):
    # Create a volume that has no category assigned
    mb = core.Core()
    model = pydagmc.DAGModel(mb)
    ent_set = pydagmc.DAGSet(model, mb.create_meshset())
    ent_set.geom_dimension = dim

    # Instantiating using the proper class (Surface, Volume, Group) should
    # result in the category tag getting assigned
    with pytest.warns(UserWarning):
        obj = getattr(pydagmc, category)(model, ent_set.handle)
    assert obj.category == category


@pytest.mark.parametrize("category,dim", [('Surface', 2), ('Volume', 3), ('Group', 4)])
def test_empty_geom_dimension(category, dim):
    # Create a volume that has no geom_dimension assigned
    mb = core.Core()
    model = pydagmc.DAGModel(mb)
    ent_set = pydagmc.DAGSet(model, mb.create_meshset())
    ent_set.category = category

    # Instantiating using the proper class (Surface, Volume, Group) should
    # result in the geom_dimension tag getting assigned
    with pytest.warns(UserWarning):
        obj = getattr(pydagmc, category)(model, ent_set.handle)
    assert obj.geom_dimension == dim


@pytest.mark.parametrize("cls", [pydagmc.Surface, pydagmc.Volume, pydagmc.Group])
def test_missing_tags(cls):
    model = pydagmc.DAGModel(core.Core())
    handle = model.mb.create_meshset()
    with pytest.raises(ValueError):
        cls(model, handle)


def test_eq(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model1 = pydagmc.DAGModel(test_file)
    model2 = pydagmc.DAGModel(test_file)

    model1_v0 = model1.volumes[1]
    model2_v0 = model2.volumes[1]

    assert model1_v0.handle == model2_v0.handle

    assert model1_v0 != model2_v0


def test_delete(fuel_pin_model):
    model = pydagmc.DAGModel(fuel_pin_model)

    fuel_group = model.groups_by_name['mat:fuel']
    fuel_group.delete()

    # attempt an operation on the group
    with pytest.raises(AttributeError, match="has no attribute 'mb'"):
        fuel_group.volumes

    # ensure the group is no longer returned by the model
    assert 'mat:fuel' not in model.groups_by_name


def test_write(request, tmpdir):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    model.volumes_by_id[1].id = 12345
    model.write_file('fuel_pin_copy.h5m')

    model = pydagmc.DAGModel('fuel_pin_copy.h5m')
    assert 12345 in model.volumes_by_id


def test_volume_value(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    exp_vols = {1: np.pi * 7**2 * 40,
                2: np.pi * (9**2 - 7**2) * 40,
                3: np.pi * (10**2 - 9**2) * 40,}
    pytest.approx(model.volumes_by_id[1].volume, exp_vols[1])
    pytest.approx(model.volumes_by_id[2].volume, exp_vols[2])
    pytest.approx(model.volumes_by_id[3].volume, exp_vols[3])


def test_area(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    exp_areas = {1: 2 * np.pi * 7 * 40,
                 2: np.pi * 7**2,
                 3: np.pi * 7**2,
                 5: 2 * np.pi * 9 * 40,
                 6: np.pi * 9**2,
                 7: np.pi * 9**2,
                 9: 2 * np.pi * 10 * 40,
                 10: np.pi * 10**2,
                 11: np.pi * 10**2 }
    for surf_id, exp_area in exp_areas.items():
        pytest.approx(model.surfaces[surf_id].area, exp_area)


def test_add_groups(request):
    test_file = str(request.path.parent / 'fuel_pin.h5m')
    model = pydagmc.DAGModel(test_file)
    volumes = model.volumes_by_id
    surfaces = model.surfaces_by_id

    for group in model.groups:
        group.delete()

    assert len(model.groups) == 0

    group_map = {("mat:fuel", 10): [1, 2],
                 ("mat:Graveyard", 50): [volumes[6]],
                 ("mat:41", 20): [3],
                 ("boundary:Reflecting", 30): [27, 28, 29],
                 ("boundary:Vacuum", 40): [surfaces[24], surfaces[25]]
                 }

    model.add_groups(group_map)

    groups = model.groups_by_name

    assert len(groups) == 5
    assert [1, 2] == sorted(groups['mat:fuel'].volume_ids)
    assert [6] == groups['mat:Graveyard'].volume_ids
    assert [3] == groups['mat:41'].volume_ids
    assert [27, 28, 29] == sorted(groups['boundary:Reflecting'].surface_ids)
    assert [24, 25] == sorted(groups['boundary:Vacuum'].surface_ids)
