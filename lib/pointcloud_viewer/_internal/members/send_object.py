from __future__ import annotations  # Postponed Evaluation of Annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pointcloud_viewer.pointcloud_viewer import PointCloudViewer

from uuid import UUID, uuid4
import numpy
from pypcd import pypcd
import open3d
from pointcloud_viewer._internal.protobuf import server_pb2
from typing import Optional


def send_pointcloud(
    self: PointCloudViewer,
    xyz: Optional[numpy.ndarray] = None,
    rgb: Optional[numpy.ndarray] = None,
    xyzrgb: Optional[numpy.ndarray] = None
) -> UUID:
    """点群をブラウザに送信し、表示させる。

    Args:
        xyz (Optional[numpy.ndarray], optional): shape が (num_points,3) で dtype が float32 の ndarray 。各行が点のx,y,z座標を表す。
        rgb (Optional[numpy.ndarray], optional): shape が (num_points,3) で dtype が uint8 の ndarray 。各行が点のr,g,bを表す。
        xyzrgb (Optional[numpy.ndarray], optional): shape が (num_points,3) で dtype が float32 の ndarray 。
            各行が点のx,y,z座標とrgbを表す。rgbは24ビットのrgb値を r<<16 + g<<8 + b のように float32 にエンコードしたもの。

    Returns:
        UUID: 表示した点群に対応するID。後から操作する際に使う
    """
    # 引数チェック
    if xyz is None and xyzrgb is None:
        raise ValueError("xyz or xyzrgb is required")
    if xyz is not None and not(len(xyz.shape) == 2 and xyz.shape[1] == 3 and xyz.dtype == "float32"):
        raise ValueError(
            "points must be float32 array of shape (num_points, 3)"
        )
    if rgb is not None:
        if xyz is None:
            raise ValueError("xyz is required with rgb")
        shape_is_valid = len(rgb.shape) == 2 and rgb.shape[1] == 3
        length_is_same = shape_is_valid and rgb.shape[0] == xyz.shape[0]
        type_is_valid = rgb.dtype == "uint8"

        if not (shape_is_valid and length_is_same and type_is_valid):
            raise ValueError(
                "colors must be uint8 array of shape (num_points, 3)"
            )
    if xyzrgb is not None and not(len(xyzrgb.shape) == 2 and xyzrgb.shape[1] == 4 and xyzrgb.dtype == "float32"):
        raise ValueError(
            "xyzrgb must be float32 array of shape (num_points, 4)"
        )

    # pcdデータ作成
    pcd: pypcd.PointCloud
    if xyz is not None:
        if rgb is not None:
            rgb_u32 = rgb.astype("uint32")
            rgb_f32: numpy.ndarray = (
                (rgb_u32[:, 0] << 16)
                + (rgb_u32[:, 1] << 8)
                + rgb_u32[:, 2]
            )
            rgb_f32.dtype = "float32"

            concatenated: numpy.ndarray = numpy.column_stack((
                xyz,
                rgb_f32,
            ))
            pcd = pypcd.make_xyz_rgb_point_cloud(concatenated)
        else:
            pcd = pypcd.make_xyz_point_cloud(xyz)
    else:
        assert xyzrgb is not None
        pcd = pypcd.make_xyz_rgb_point_cloud(xyzrgb)

    pcd_bytes = pcd.save_pcd_to_buffer()

    # 送信
    cloud = server_pb2.AddObject.PointCloud()
    cloud.pcd_data = pcd_bytes

    add_obj = server_pb2.AddObject()
    add_obj.point_cloud.CopyFrom(cloud)

    obj = server_pb2.ServerCommand()
    obj.add_object.CopyFrom(add_obj)

    uuid = uuid4()
    self._send_data(obj, uuid)
    ret = self._wait_until(uuid)
    if ret.result.HasField("failure"):
        raise RuntimeError(ret.result.failure)
    if not ret.result.HasField("success"):
        raise RuntimeError("unexpected response")
    return UUID(hex=ret.result.success)


def send_lineset_from_open3d(
    self: PointCloudViewer,
    lineset: open3d.geometry.LineSet,
) -> UUID:
    """LineSetをブラウザに送信し、表示させる。

    :param lineset: LineSet。
    :type lineset: open3d.geometry.LineSet

    Returns:
        UUID: 表示したLineSetに対応するID。後から操作する際に使う
    """
    pb_lineset = server_pb2.AddObject.LineSet()
    for v in numpy.asarray(lineset.points):
        p = server_pb2.VecXYZf()
        p.x = v[0]
        p.y = v[1]
        p.z = v[2]
        pb_lineset.points.append(p)
    for l in numpy.asarray(lineset.lines):
        pb_lineset.from_index.append(l[0])
        pb_lineset.to_index.append(l[1])

    add_obj = server_pb2.AddObject()
    add_obj.line_set.CopyFrom(pb_lineset)
    obj = server_pb2.ServerCommand()
    obj.add_object.CopyFrom(add_obj)

    uuid = uuid4()
    self._send_data(obj, uuid)
    ret = self._wait_until(uuid)
    if ret.result.HasField("failure"):
        raise RuntimeError(ret.result.failure)
    if not ret.result.HasField("success"):
        raise RuntimeError("unexpected response")
    return UUID(hex=ret.result.success)


def send_overlay_text(
    self: PointCloudViewer,
    text: str,
    x: float = 0,
    y: float = 0,
    z: float = 0,
) -> UUID:
    """特定の座標を左上として文字列をオーバーレイさせる。

    :param text: 表示させる文字列
    :type text: str
    :param x: オーバーレイが追従する点のx座標
    :type x: float, optional
    :param y: オーバーレイが追従する点のy座標
    :type y: float, optional
    :param z: オーバーレイが追従する点のz座標
    :type z: float, optional

    Returns:
        UUID: オーバーレイに対応するID。後から操作する際に使う
    """
    overlay = server_pb2.AddObject.Overlay()
    position = server_pb2.VecXYZf()
    position.x = x
    position.y = y
    position.z = z
    overlay.position.CopyFrom(position)
    overlay.text = text
    add_obj = server_pb2.AddObject()
    add_obj.overlay.CopyFrom(overlay)
    obj = server_pb2.ServerCommand()
    obj.add_object.CopyFrom(add_obj)

    uuid = uuid4()
    self._send_data(obj, uuid)
    ret = self._wait_until(uuid)
    if ret.result.HasField("failure"):
        raise RuntimeError(ret.result.failure)
    if not ret.result.HasField("success"):
        raise RuntimeError("unexpected response")
    return UUID(hex=ret.result.success)
