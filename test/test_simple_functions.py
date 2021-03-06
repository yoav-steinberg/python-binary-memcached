import unittest
import bmemcached
from bmemcached.protocol import Protocol


class MemcachedTests(unittest.TestCase):
    def setUp(self):
        self.server = '127.0.0.1:11211'
        self.server = '/tmp/memcached.sock'
        self.client = bmemcached.Client(self.server) #, 'user', 'password')

    def tearDown(self):
        self.reset()
        self.client.disconnect_all()
        
    def reset(self):
        self.client.delete('test_key')
        self.client.delete('test_key2')

    def testSet(self):
        self.assertTrue(self.client.set('test_key', 'test'))

    def testSetMulti(self):
        self.assertTrue(self.client.set_multi({
            'test_key': 'value',
            'test_key2': 'value2'}))

    def testSetMultiBigData(self):
        self.client.set_multi(dict(
                (unicode(k).encode(), b'value') for k in range(32767)))

    def testGet(self):
        self.client.set('test_key', 'test')
        self.assertEqual('test', self.client.get('test_key'))

    def testCas(self):
        value, cas = self.client.gets('nonexistant')
        self.assertTrue(value is None)
        self.assertTrue(cas is None)

        # cas() with a cas value of None is equivalent to add.
        self.assertTrue(self.client.cas('test_key', 'test', cas))
        self.assertFalse(self.client.cas('test_key', 'testX', cas))

        # Load the CAS key.
        value, cas = self.client.gets('test_key')
        self.assertEqual('test', value)
        self.assertTrue(cas is not None)

        # Overwrite test_key only if it hasn't changed since we read it.
        self.assertTrue(self.client.cas('test_key', 'test2', cas))
        self.assertEqual(self.client.get('test_key'), 'test2')

        # This call won't overwrite the value, since the CAS key is out of date.
        self.assertFalse(self.client.cas('test_key', 'test3', cas))
        self.assertEqual(self.client.get('test_key'), 'test2')

    def testCasDelete(self):
        self.assertTrue(self.client.set('test_key', 'test'))
        value, cas = self.client.gets('test_key')

        # If a different CAS value is supplied, the key is not deleted.
        self.assertFalse(self.client.delete('test_key', cas=cas+1))
        self.assertEqual('test', self.client.get('test_key'))

        # If the correct CAS value is supplied, the key is deleted.
        self.assertTrue(self.client.delete('test_key', cas=cas))
        self.assertEqual(None, self.client.get('test_key'))

    def testMultiCas(self):
        # Set multiple values, some using CAS and some not.  True is returned, because
        # both values were stored.
        self.assertTrue(self.client.set_multi({
            ('test_key', 0): 'value1',
            'test_key2': 'value2',
        }))

        self.assertEqual(self.client.get('test_key'), 'value1')
        self.assertEqual(self.client.get('test_key2'), 'value2')

        # A CAS value of 0 means add.  The value already exists, so this won't overwrite it.
        # False is returned, because not all items were stored, but test_key2 is still stored.
        self.assertFalse(self.client.set_multi({
            ('test_key', 0): 'value3',
            'test_key2': 'value3',
        }))

        self.assertEqual(self.client.get('test_key'), 'value1')
        self.assertEqual(self.client.get('test_key2'), 'value3')

        # Update with the correct CAS value.
        value, cas = self.client.gets('test_key')
        self.assertTrue(self.client.set_multi({
            ('test_key', cas): 'value4',
        }))
        self.assertEqual(self.client.get('test_key'), 'value4')

    def testGetMultiCas(self):
        self.client.set('test_key', 'value1')
        self.client.set('test_key2', 'value2')

        value1, cas1 = self.client.gets('test_key')
        value2, cas2 = self.client.gets('test_key2')

        # Batch retrieve items and their CAS values, and verify that they match
        # the values we got by looking them up individually.
        values = self.client.get_multi(['test_key', 'test_key2'], get_cas=True)
        self.assertEqual(values.get('test_key')[0], 'value1')
        self.assertEqual(values.get('test_key2')[0], 'value2')

    def testGetEmptyString(self):
        self.client.set('test_key', '')
        self.assertEqual('', self.client.get('test_key'))

    def testGetMulti(self):
        self.assertTrue(self.client.set_multi({
            'test_key': 'value',
            'test_key2': 'value2'
        }))
        self.assertEqual({'test_key': 'value', 'test_key2': 'value2'},
                         self.client.get_multi(['test_key', 'test_key2']))
        self.assertEqual({'test_key': 'value', 'test_key2': 'value2'},
                         self.client.get_multi(['test_key', 'test_key2', 'nothere']))

    def testGetLong(self):
        self.client.set('test_key', 1L)
        value = self.client.get('test_key')
        self.assertEqual(1L, value)
        self.assertTrue(isinstance(value, long))

    def testGetInteger(self):
        self.client.set('test_key', 1)
        value = self.client.get('test_key')
        self.assertEqual(1, value)
        self.assertTrue(isinstance(value, int))

    def testGetObject(self):
        self.client.set('test_key', {'a': 1})
        value = self.client.get('test_key')
        self.assertTrue(isinstance(value, dict))
        self.assertTrue('a' in value)
        self.assertEqual(1, value['a'])

    def testDelete(self):
        self.client.set('test_key', 'test')
        self.assertTrue(self.client.delete('test_key'))
        self.assertEqual(None, self.client.get('test_key'))

    def testDeleteUnknownKey(self):
        self.assertTrue(self.client.delete('test_key'))

    def testAddPass(self):
        self.assertTrue(self.client.add('test_key', 'test'))

    def testAddFail(self):
        self.client.add('test_key', 'value')
        self.assertFalse(self.client.add('test_key', 'test'))

    def testReplacePass(self):
        self.client.add('test_key', 'value')
        self.assertTrue(self.client.replace('test_key', 'value2'))
        self.assertEqual('value2', self.client.get('test_key'))

    def testReplaceFail(self):
        self.assertFalse(self.client.replace('test_key', 'value'))

    def testIncrement(self):
        self.assertEqual(0, self.client.incr('test_key', 1))
        self.assertEqual(1, self.client.incr('test_key', 1))

    def testDecrement(self):
        self.assertEqual(0, self.client.decr('test_key', 1))
        self.assertEqual(0, self.client.decr('test_key', 1))

    def testFlush(self):
        self.client.set('test_key', 'test')
        self.assertTrue(self.client.flush_all())
        self.assertEqual(None, self.client.get('test_key'))

    def testStats(self):
        stats = self.client.stats()[self.server]
        self.assertTrue('pid' in stats)

        stats = self.client.stats('settings')[self.server]
        self.assertTrue('verbosity' in stats)

        stats = self.client.stats('slabs')[self.server]
        self.assertTrue('1:get_hits' in stats)

    def testReconnect(self):
        self.client.set('test_key', 'test')
        self.client.disconnect_all()
        self.assertEqual('test', self.client.get('test_key'))
