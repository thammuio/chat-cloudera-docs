from milvus import default_server
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import subprocess

import app.embeddings.embeddings_utils as model_embedding

import os
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer



def create_milvus_collection(collection_name, dim):
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)

    fields = [
        FieldSchema(name='content', dtype=DataType.VARCHAR, description='actual content or document text', max_length=5000),  # Adjust max_length as needed
        FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, description='embedding vectors', dim=dim),
        FieldSchema(name='id', dtype=DataType.INT64, is_primary=True, auto_id=True),  # Use an auto-generated ID
    ]
    schema = CollectionSchema(fields=fields, description='knowledge base content search')
    collection = Collection(name=collection_name, schema=schema)

    # create IVF_FLAT index for collection.
    index_params = {
        'metric_type': 'IP',
        'index_type': "IVF_FLAT",
        'params': {"nlist": 2048}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    return collection

# Create an embedding for given text/doc and insert it into Milvus Vector DB
def insert_embedding(collection, content, text):
    embedding = model_embedding.get_embeddings(text)
    data = [[content], [embedding]]
    collection.insert(data)


def main():
    if os.getenv('VECTOR_DB').upper() == "MILVUS":
        # Reset the vector database files
        kb_name = os.getenv('KB_VECTOR_INDEX')
        new_base_dir = f"milvus-data-{kb_name}"
        default_server.set_base_dir(new_base_dir)
        default_server.start()
        

        try:
            connections.connect(alias='default', host='localhost', port=default_server.listen_port)
            print(utility.get_server_version())

            # Create/Recreate the Milvus collection
            collection_name = kb_name
            collection = create_milvus_collection(collection_name, 768)

            print("Milvus database is up and collection is created")

            # Read KB documents in ./data directory and insert embeddings into Vector DB for each doc
            doc_dir = f'./data/{kb_name}'
            for file in Path(doc_dir).glob(f'**/*.csv'):
                print("Processing CSV file: %s" % file.name)
                df = pd.read_csv(file)

                for index, row in df.iterrows():
                    # Combine all relevant fields to create text for embedding
                    text = f"Question: {row['Question']} Answer: {row['Answer']}"
                    content = text  # Store the entire text as content
                    insert_embedding(collection, content, text)

            collection.flush()
            print('Total number of inserted embeddings is {}.'.format(collection.num_entities))
            print('Finished loading Knowledge Base embeddings into Milvus')

        except Exception as e:
            default_server.stop()
            raise e

        default_server.stop()



if __name__ == "__main__":
    main()