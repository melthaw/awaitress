import unittest


class TestFixedStreamReceiver(unittest.TestCase):
    def _makeOne(self, cl, buf):
        from awaitress.receiver import FixedStreamReceiver

        return FixedStreamReceiver(cl, buf)

    def test_received_remain_lt_1(self):
        buf = DummyBuffer()
        inst = self._makeOne(0, buf)
        result = inst.received("a")
        self.assertEqual(result, 0)
        self.assertEqual(inst.completed, True)

    def test_received_remain_lte_datalen(self):
        buf = DummyBuffer()
        inst = self._makeOne(1, buf)
        result = inst.received("aa")
        self.assertEqual(result, 1)
        self.assertEqual(inst.completed, True)
        self.assertEqual(inst.completed, 1)
        self.assertEqual(inst.remain, 0)
        self.assertEqual(buf.data, ["a"])

    def test_received_remain_gt_datalen(self):
        buf = DummyBuffer()
        inst = self._makeOne(10, buf)
        result = inst.received("aa")
        self.assertEqual(result, 2)
        self.assertEqual(inst.completed, False)
        self.assertEqual(inst.remain, 8)
        self.assertEqual(buf.data, ["aa"])

    def test_getfile(self):
        buf = DummyBuffer()
        inst = self._makeOne(10, buf)
        self.assertEqual(inst.getfile(), buf)

    def test_getbuf(self):
        buf = DummyBuffer()
        inst = self._makeOne(10, buf)
        self.assertEqual(inst.getbuf(), buf)

    def test___len__(self):
        buf = DummyBuffer(["1", "2"])
        inst = self._makeOne(10, buf)
        self.assertEqual(inst.__len__(), 2)


class TestChunkedReceiver(unittest.TestCase):
    def _makeOne(self, buf):
        from awaitress.receiver import ChunkedReceiver

        return ChunkedReceiver(buf)

    def test_alreadycompleted(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        inst.completed = True
        result = inst.received(b"a")
        self.assertEqual(result, 0)
        self.assertEqual(inst.completed, True)

    def test_received_remain_gt_zero(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        inst.chunk_remainder = 100
        result = inst.received(b"a")
        self.assertEqual(inst.chunk_remainder, 99)
        self.assertEqual(result, 1)
        self.assertEqual(inst.completed, False)

    def test_received_control_line_notfinished(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        result = inst.received(b"a")
        self.assertEqual(inst.control_line, b"a")
        self.assertEqual(result, 1)
        self.assertEqual(inst.completed, False)

    def test_received_control_line_finished_garbage_in_input(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        result = inst.received(b"garbage\r\n")
        self.assertEqual(result, 9)
        self.assertTrue(inst.error)

    def test_received_control_line_finished_all_chunks_not_received(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        result = inst.received(b"a;discard\r\n")
        self.assertEqual(inst.control_line, b"")
        self.assertEqual(inst.chunk_remainder, 10)
        self.assertEqual(inst.all_chunks_received, False)
        self.assertEqual(result, 11)
        self.assertEqual(inst.completed, False)

    def test_received_control_line_finished_all_chunks_received(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        result = inst.received(b"0;discard\r\n")
        self.assertEqual(inst.control_line, b"")
        self.assertEqual(inst.all_chunks_received, True)
        self.assertEqual(result, 11)
        self.assertEqual(inst.completed, False)

    def test_received_trailer_startswith_crlf(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        inst.all_chunks_received = True
        result = inst.received(b"\r\n")
        self.assertEqual(result, 2)
        self.assertEqual(inst.completed, True)

    def test_received_trailer_startswith_lf(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        inst.all_chunks_received = True
        result = inst.received(b"\n")
        self.assertEqual(result, 1)
        self.assertEqual(inst.completed, False)

    def test_received_trailer_not_finished(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        inst.all_chunks_received = True
        result = inst.received(b"a")
        self.assertEqual(result, 1)
        self.assertEqual(inst.completed, False)

    def test_received_trailer_finished(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        inst.all_chunks_received = True
        result = inst.received(b"abc\r\n\r\n")
        self.assertEqual(inst.trailer, b"abc\r\n\r\n")
        self.assertEqual(result, 7)
        self.assertEqual(inst.completed, True)

    def test_getfile(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        self.assertEqual(inst.getfile(), buf)

    def test_getbuf(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        self.assertEqual(inst.getbuf(), buf)

    def test___len__(self):
        buf = DummyBuffer(["1", "2"])
        inst = self._makeOne(buf)
        self.assertEqual(inst.__len__(), 2)

    def test_received_chunk_is_properly_terminated(self):
        buf = DummyBuffer()
        inst = self._makeOne(buf)
        data = b"4\r\nWiki\r\n"
        result = inst.received(data)
        self.assertEqual(result, len(data))
        self.assertEqual(inst.completed, False)
        self.assertEqual(buf.data[0], b"Wiki")

    def test_received_chunk_not_properly_terminated(self):
        from awaitress.utilities import BadRequest

        buf = DummyBuffer()
        inst = self._makeOne(buf)
        data = b"4\r\nWikibadchunk\r\n"
        result = inst.received(data)
        self.assertEqual(result, len(data))
        self.assertEqual(inst.completed, False)
        self.assertEqual(buf.data[0], b"Wiki")
        self.assertEqual(inst.error.__class__, BadRequest)

    def test_received_multiple_chunks(self):
        from awaitress.utilities import BadRequest

        buf = DummyBuffer()
        inst = self._makeOne(buf)
        data = (
            b"4\r\n"
            b"Wiki\r\n"
            b"5\r\n"
            b"pedia\r\n"
            b"E\r\n"
            b" in\r\n"
            b"\r\n"
            b"chunks.\r\n"
            b"0\r\n"
            b"\r\n"
        )
        result = inst.received(data)
        self.assertEqual(result, len(data))
        self.assertEqual(inst.completed, True)
        self.assertEqual(b"".join(buf.data), b"Wikipedia in\r\n\r\nchunks.")
        self.assertEqual(inst.error, None)

    def test_received_multiple_chunks_split(self):
        from awaitress.utilities import BadRequest

        buf = DummyBuffer()
        inst = self._makeOne(buf)
        data1 = b"4\r\nWiki\r"
        result = inst.received(data1)
        self.assertEqual(result, len(data1))

        data2 = (
            b"\n5\r\n"
            b"pedia\r\n"
            b"E\r\n"
            b" in\r\n"
            b"\r\n"
            b"chunks.\r\n"
            b"0\r\n"
            b"\r\n"
        )

        result = inst.received(data2)
        self.assertEqual(result, len(data2))

        self.assertEqual(inst.completed, True)
        self.assertEqual(b"".join(buf.data), b"Wikipedia in\r\n\r\nchunks.")
        self.assertEqual(inst.error, None)


class DummyBuffer(object):
    def __init__(self, data=None):
        if data is None:
            data = []
        self.data = data

    def append(self, s):
        self.data.append(s)

    def getfile(self):
        return self

    def __len__(self):
        return len(self.data)
