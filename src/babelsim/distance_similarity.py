import neo4j
from neo4j import GraphDatabase
import babelnet as bn

class DistanceSimilarity:
    def __init__(self, 
                 database='neo4j', 
                 URI = "bolt://localhost:7687", 
                 USER='giovanni', 
                 PASSWD='BabeldistGraph',
                 root_node_id='bn:00062164n') -> None:
        
        self._database = database
        self._driver = GraphDatabase.driver(URI, auth=(USER, PASSWD))
        self._root_node_id = root_node_id
        
        self._random_node_query = " MATCH (a:Synset) RETURN a.synsetID as synsetID ORDER BY rand() LIMIT 1"
        self._count_nodes_query = " MATCH (s:Synset) RETURN count(s) as numNodes "
        self._count_edges_query = " MATCH ()-[r:IS_A]->() RETURN count(r) as numEdges "

        self._shortestPath_query = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = shortestPath((s1)-[:IS_A*..12]-(s2))
        RETURN p as shortest_path, length(p) as length_shortestPath """
        
        self._wup_query = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = (s1)-[:IS_A*..12]->(common_node:Synset)<-[:IS_A*..12]-(s2) 
        WITH s1, s2, common_node, length(p) AS len_p ORDER BY len_p ASC LIMIT 1
        MATCH (root:Synset {synsetID:  $root_node_id})
        WITH root, s1, s2, common_node,
        CASE root.synsetID <> common_node.synsetID
            WHEN True THEN LENGTH(shortestPath((common_node)-[:IS_A*1..12]-(root)))
            ELSE 1
        END AS LCS_depth
        MATCH s1_sp = shortestPath((s1)-[:IS_A*1..12]-(root))
        MATCH s2_sp = shortestPath((s2)-[:IS_A*1..12]-(root))
        WITH length(s1_sp) AS dist_s1_root, length(s2_sp) AS dist_s2_root, LCS_depth
        RETURN (toFloat(LCS_depth) / (dist_s1_root + dist_s2_root)) AS wup_similarity """

        self._lch_query = """
        MATCH t = (root:Synset {synsetID: $root_id})<-[:IS_A*1..12]-(child:Synset) 
        WHERE NOT (child)<-[:IS_A]-()
        WITH length(t) AS D ORDER BY D DESC LIMIT 1
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH shortest_path = shortestPath((s1)-[:IS_A*..12]-(s2))
        WITH D, length(shortest_path) as length_sp
        RETURN -log(toFloat(length_sp) / (2*D)) as lch_similarity, D as taxonomy_length, length_sp """

        self._path_query = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = shortestPath((s1)-[:IS_A*..12]-(s2))
        RETURN 1.0/length(p) as path_similarity """

        self._community_path_query = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = shortestPath((s1)-[:IS_A*..12]-(s2))
        WITH p, NODES(p) AS theNodes
        UNWIND theNodes as singleNode
        WITH LENGTH(p) AS l, COUNT(DISTINCT singleNode.intermediateCommunities) AS c
        RETURN toFloat(1) / (l + c - 1) AS community_path_similarity """

        self._community_path_query_2 = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = shortestPath((s1)-[:IS_A*..12]-(s2))
        WITH p, NODES(p) AS theNodes
        UNWIND theNodes as singleNode
        WITH LENGTH(p) AS l, COUNT(DISTINCT singleNode.intermediateCommunities) AS c
        RETURN -log(toFloat(1) / (l + c - 1)) AS community_path_similarity_2 """

    def get_random_synset_id(self):
        return self._driver.execute_query(self._random_node_query, 
                                         result_transformer_=neo4j.Result.data,
                                         database_=self._database)[0]['synsetID']

    def get_shortest_path_length(self, s1_id: str, s2_id: str):
        p = self._driver.execute_query(
            self._shortestPath_query, 
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)
        return p[0]['length_shortestPath']

    def shortest_path_synsets_lemmas(self, s1_id: str, s2_id: str):
        from babelnet import BabelSynsetID
        shortest_path = self._driver.execute_query(
            self._shortestPath_query, 
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)

        for item in shortest_path[0]['shortest_path']:
            if type(item) is dict and 'synsetID' in item.keys():
                try:
                    print(f"{item['synsetID']}, \
                          {BabelSynsetID(item['synsetID']).to_synset().main_sense().full_lemma}")
                except Exception as e:
                    print(e.args[0])

    def wup_similarity(self, s1_id: str, s2_id: str):
        return self._driver.execute_query(
            self._wup_query,
            {'root_node_id': self._root_node_id,
             'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]['wup_similarity']

    def lch_similarity(self, s1_id: str, s2_id: str):
        return self._driver.execute_query(
            self._lch_query,
            {'root_id': self._root_node_id,
             'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]['lch_similarity']

    def path_similarity(self, s1_id: str, s2_id: str):
        return self._driver.execute_query(
            self._path_query,
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_='neo4j',
            result_transformer_=neo4j.Result.data)[0]['path_similarity']

    def community_path_similarity(self, s1_id: str, s2_id: str):
        return self._driver.execute_query(
            self._community_path_query,
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]['community_path_similarity']

    def community_path_similarity_2(self, s1_id: str, s2_id: str):
        return self._driver.execute_query(
            self._community_path_query_2,
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]['community_path_similarity_2']

    def evaluate_similarities(self, s1_id: str, s2_id: str, verbose=True):
        if verbose:
            from babelnet import BabelSynsetID
            s1, s2 = BabelSynsetID(s1_id).to_synset(), BabelSynsetID(s2_id).to_synset()
            print(f'{s1_id} - {s1} - {s1.main_gloss()}')
            print(f'{s2_id} - {s2} - {s2.main_gloss()}')
        print(f'wup:\t\t{   round(self.wup_similarity(s1_id, s2_id), 3)}')
        print(f'lch:\t\t{   round(self.lch_similarity(s1_id, s2_id), 3)}')
        print(f'path:\t\t{  round(self.path_similarity( s1_id, s2_id), 3)}')
        print(f'path_com:\t{round(self.community_path_similarity(s1_id, s2_id), 3)}')
        print(f'path_com_2:\t{round(self.community_path_similarity_2(s1_id, s2_id), 3)}')

    def nodes_with_common_ancestor(self, ancestor_id):
        number_of_nodes_with_ancestor_query = "MATCH (n:Synset)-[:IS_A*]->(ancestor:Synset {synsetID: $ancestorID}) RETURN count(n)"
        
        n = self._driver.execute_query(
            number_of_nodes_with_ancestor_query, 
            {'ancestorID': ancestor_id},
            result_transformer_=neo4j.Result.data)[0]['count(n)']
        tot_nodes = self._driver.execute_query(
            self._count_nodes_query,                          
            result_transformer_=neo4j.Result.data)[0]['numNodes']
        
        print(f'{n} nodes with ancestor bn:00035942n of {tot_nodes} nodes, {round(n*100/tot_nodes, 2)}%')

    def print_neo4j_graph_statistics(self):
        num_nodes = self._driver.execute_query(
            query_="MATCH (s:Synset) RETURN COUNT(s) AS numNodes",
            database_=self._database, result_transformer_=neo4j.Result.data)[0]['numNodes']
        num_edges = self._driver.execute_query(
            query_="MATCH ()-[r:IS_A]-() RETURN COUNT(r) AS numEdges",
            database_=self._database, result_transformer_=neo4j.Result.data)[0]['numEdges']
        
        print(f'Database {self._database} contains {num_nodes} nodes, {num_edges} relationships.')

    def random_example(self, verbose=True):
        id1, id2 = self.get_random_synset_id(), self.get_random_synset_id()
        self.evaluate_similarities(id1, id2, verbose)
