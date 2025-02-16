import argparse
import unittest
import os
from unittest.mock import MagicMock, patch
from deply.deply_runner import DeplyRunner


class TestDeplyRunnerArguments(unittest.TestCase):

    def setUp(self):
        self.mock_args = MagicMock()
        self.runner = DeplyRunner(self.mock_args)

    @patch('os.cpu_count', return_value=8)
    def test_workers_count_no_parallel(self, _mock_cpu_count):
        self.mock_args.parallel = None
        self.assertEqual(self.runner._get_workers_count(), 1)

    @patch('os.cpu_count', return_value=8)
    def test_workers_count_parallel_zero(self, _mock_cpu_count):
        self.mock_args.parallel = 0
        self.assertEqual(self.runner._get_workers_count(), 8)

    @patch('os.cpu_count', return_value=8)
    def test_workers_count_parallel_less_than_cpu(self, _mock_cpu_count):
        self.mock_args.parallel = 2
        self.assertEqual(self.runner._get_workers_count(), 2)

    @patch('os.cpu_count', return_value=8)
    def test_workers_count_parallel_more_than_cpu(self, _mock_cpu_count):
        self.mock_args.parallel = 100
        self.assertEqual(self.runner._get_workers_count(), 8)
