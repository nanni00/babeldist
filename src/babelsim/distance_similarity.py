import numpy as np
from pprint import pprint 
import neo4j
from neo4j import GraphDatabase


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
        RETURN p as shortest_path, LENGTH(p) as shortest_path_length """
        
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
        RETURN 2 * (toFloat(LCS_depth) / (dist_s1_root + dist_s2_root)) AS wup_similarity, 
            LCS_depth, dist_s1_root, dist_s2_root """

        self._lch_query = """
        MATCH t = (root:Synset {synsetID: $root_id})<-[:IS_A*1..12]-(child:Synset) 
        WHERE NOT (child)<-[:IS_A]-()
        WITH length(t) AS D ORDER BY D DESC LIMIT 1
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH shortest_path = shortestPath((s1)-[:IS_A*..12]-(s2))
        WITH D, length(shortest_path) as shortest_path_length
        RETURN -log(toFloat(shortest_path_length) / (2*D)) as lch_similarity, 
            D, shortest_path_length """

        self._path_query = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = shortestPath((s1)-[:IS_A*..12]-(s2))
        RETURN 1.0/length(p) as path_similarity, length(p) as shortest_path_length"""

        self._community_path_query = """
        MATCH (s1:Synset {synsetID: $synsetID_1})
        MATCH (s2:Synset {synsetID: $synsetID_2})
        MATCH p = shortestPath((s1)-[:IS_A*..12]-(s2))
        RETURN p as shortest_path, LENGTH(p) as shortest_path_length """

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
        return p[0]['shortest_path_length']

    def shortest_path_synsets_lemmas(self, s1_id: str, s2_id: str):
        shortest_path = self._driver.execute_query(
            self._shortestPath_query, 
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]['shortest_path']

        for item in shortest_path:
            if type(item) is dict:
                print(f"{item['synsetID']}, {item['lemma']}")
                
    def wup_similarity(self, s1_id: str, s2_id: str):
        res = self._driver.execute_query(
            self._wup_query,
            {'root_node_id': self._root_node_id,
             'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]
        return res['wup_similarity'], res['LCS_depth'], res['dist_s1_root'], res['dist_s2_root']

    def lch_similarity(self, s1_id: str, s2_id: str):
        res = self._driver.execute_query(
            self._lch_query,
            {'root_id': self._root_node_id,
             'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]
        return res['lch_similarity'], res['shortest_path_length'], res['D']
    
    def path_similarity(self, s1_id: str, s2_id: str):
        res = self._driver.execute_query(
            self._path_query,
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]
        return res['path_similarity'], res['shortest_path_length']
    
    def get_community_distance(self, s1_id: str, s2_id: str, path=None):
        if path == None:
            result = self._driver.execute_query(
                self._community_path_query,
                {'synsetID_1': s1_id,
                 'synsetID_2': s2_id},
                database_=self._database,
                result_transformer_=neo4j.Result.data)[0]
            path = result['shortest_path']

        comcount = 0 
        first_synset = path.pop(0)
        for x in (synset for synset in path if synset != 'IS_A'):
            if set(first_synset['communityIDs']).intersection(set(x['communityIDs'])) == set():
                comcount += 1
            first_synset = x
        return comcount

    def community_path_similarity(self, s1_id: str, s2_id: str):
        result = self._driver.execute_query(
            self._community_path_query,
            {'synsetID_1': s1_id,
             'synsetID_2': s2_id},
            database_=self._database,
            result_transformer_=neo4j.Result.data)[0]
        sp, splen = result['shortest_path'], result['shortest_path_length']

        comcount = self.get_community_distance(s1_id, s2_id, sp)
        return -np.log(1 / (splen + comcount)), splen, comcount

    def evaluate_similarities(self, s1_id: str, s2_id: str, verbose=True):
        wup = self.wup_similarity(s1_id, s2_id)
        lch = self.lch_similarity(s1_id, s2_id)
        path = self.path_similarity(s1_id, s2_id)
        cp = self.community_path_similarity(s1_id, s2_id)

        if verbose:
            from babelnet import BabelSynsetID
            s1, s2 = BabelSynsetID(s1_id).to_synset(), BabelSynsetID(s2_id).to_synset()
            print(f'{s1_id} - {s1.main_sense().full_lemma} - {s1.main_gloss()}')
            print(f'{s2_id} - {s2.main_sense().full_lemma} - {s2.main_gloss()}')
            
            print(f'wup:\t\t{round(wup[0], 3)}\tLCS_depth={wup[1]}\td_A_root={wup[2]}\td_B_root={wup[3]}')
            print(f'lch:\t\t{round(lch[0], 3)}\tsp_len={lch[1]}\tD={lch[2]}')
            print(f'path:\t\t{round(path[0], 3)}\tsp_len={path[1]}')
            print(f'path_com:\t{round(cp[0], 3)}\tsp_len={cp[1]}\tcomcount={cp[2]}')
        else:
            print(f'{s1_id}, {s2_id}')
            print(f'wup:\t\t{round(wup[0], 3)}')
            print(f'lch:\t\t{round(lch[0], 3)}')
            print(f'path:\t\t{round(path[0], 3)}')
            print(f'path_com:\t{round(cp[0], 3)}')

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


# ds = DistanceSimilarity(database='BabelExpDBnoLemma')

# ds.evaluate_similarities('bn:00015267n', 'bn:00016606n')
# ds.evaluate_similarities('bn:00015267n', 'bn:00044576n')
# ds.evaluate_similarities('bn:01174701n', 'bn:20243349n')


#while (s := input('Another example? ')) != 'n':
#    ds.evaluate_similarities(ds.get_random_synset_id(), ds.get_random_synset_id())

