from typing import Any

from pymongo import InsertOne, UpdateOne

AdditionalInfo = dict[str, Any]
Document = dict[str, Any]
BulkWriteTask = UpdateOne | InsertOne
