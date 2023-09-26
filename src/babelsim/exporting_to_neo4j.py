import os
import sys
sys.path.append(os.path.curdir)
from src.utils import utils
import time

import neo4j
from neo4j import GraphDatabase

from babelnet import BabelSynsetID
from babelnet.data.relation import BabelPointer

from zerorpc import TimeoutExpired, LostRemote


def run_no_exception(session: neo4j.Session, query: str):
    try:
        session.run(query)
    except Exception:
        pass

merge_graph_query = """
UNWIND $hyponyms_list as hyponymID
MERGE (s:Synset {synsetID: $synsetID})
MERGE (hyponym:Synset {synsetID: hyponymID})
WITH s, hyponym
WHERE s.synsetID <> hyponym.synsetID
MERGE (s)<-[:IS_A]-(hyponym) """

count_nodes_query = """
MATCH (s:Synset)
RETURN count(s) """

count_edges_query = """
MATCH ()-[r:IS_A]->()
RETURN count(r) """


def exporting_babelnet_to_neo4j(start_synset_id=['bn:00062164n'], 
                                max_synsets_visited=100,
                                queue_type='list',
                                export_anything=False,
                                default_max_export=100,
                                database='neo4j', URI="bolt://localhost:7687", USER="giovanni", PASSWD="BabeldistGraph"):

    # EXPORTING BABELNET TO NEO4J - ONLY SYNSET IDs, NO LEMMA OR OTHER PROPERTIES
    fname = utils.get_next_logfile_number('exporting_neo4j', extension='log')

    start_synset_id = start_synset_id
    max_synset_visited, n = max_synsets_visited, 0
    visited = set()
    q = utils.Queue(queue_type, [BabelSynsetID(id) for id in start_synset_id])

    URI = URI
    AUTH = (USER, PASSWD)
    
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session(database=database) as session:
            run_no_exception(session, 'CREATE CONSTRAINT FOR (s:Synset) REQUIRE s.synsetID IS UNIQUE')
            tx = session.begin_transaction()
            
            start_n, start_r = tx.run(count_nodes_query).values()[0][0], tx.run(count_edges_query).values()[0][0]
            
            with open(fname, 'x') as logfname:
                start_t = time.time()
                while q.q and n < max_synset_visited:
                    pb = utils.get_progress_bar(int((n / max_synset_visited) * 100))
                    print(pb, end='\r')                

                    try:
                        synset = q.pop_item().to_synset()
                        hyponym_edges = synset.outgoing_edges(BabelPointer.ANY_HYPONYM)
                        if len(hyponym_edges) == 0: continue
                        elif not export_anything and len(hyponym_edges) > 100:
                            a = input(f'Synset {synset.id} {synset.main_sense().full_lemma} has {len(hyponym_edges)}: export them all? (y/n) ')
                            if a == 'n':
                                hyponym_edges = hyponym_edges[:min(default_max_export, len(hyponym_edges))]                        
                        n += 1
                    except (TimeoutExpired, LostRemote) as e:
                        e.with_traceback()
                        hyponym_edges = []

                    hl = []
                    for edge in hyponym_edges:                        
                        if edge.id_target not in visited and edge.id_target not in q.q:                        
                            q.add_item(edge.id_target)
                            visited.add(edge.id_target)    
                        hl.append(edge.id_target.id)

                    try:
                        tx.run(merge_graph_query, {
                            'synsetID': str(synset.id), 
                            'hyponyms_list': str(hl) })
                    except Exception as e:
                        e.with_traceback()

                    if n % 1000 == 0:
                        tx.commit()
                        tx = session.begin_transaction()

                end_n, end_r = tx.run(count_nodes_query).values()[0][0], tx.run(count_edges_query).values()[0][0]
                tx.commit()
                print(f'Added {end_n - start_n} nodes, added {end_r - start_r} edges.')
                
                logfname.write(f'start_node={start_synset_id}\n')
                logfname.write(f'max_visits={max_synset_visited}\n')
                if q.q == []: logfname.write('Queue empy\n')
                if n == max_synset_visited: logfname.write('Reached max visits\n')
                logfname.write(f'Added {end_n - start_n} nodes, added {end_r - start_r} edges.')
                end_t = time.time()
                m, s = divmod(end_t - start_t, 60)
                logfname.write(f'total_time,{int(m)}m,{int(s)}s') 

exporting_babelnet_to_neo4j(max_synsets_visited=1, database='testcommunities')