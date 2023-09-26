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


def _run_no_exception(session: neo4j.Session, query: str):
    try:
        session.run(query)
    except Exception:
        pass

_merge_graph_query = """
UNWIND $hyponyms as hyponym_data
MERGE (s:Synset {synsetID: $synsetID, lemma: $synset_lemma})
MERGE (hyponym:Synset {synsetID: hyponym_data[0], lemma: hyponym_data[1]})
WITH s, hyponym
WHERE s.synsetID <> hyponym.synsetID
MERGE (s)<-[:IS_A]-(hyponym) """

_count_nodes_query = """
MATCH (s:Synset)
RETURN count(s) """

_count_edges_query = """
MATCH ()-[r:IS_A]->()
RETURN count(r) """


def exporting_babelnet_to_neo4j(start_synset_id=['bn:00062164n'], 
                                max_synsets_visited=100,
                                queue_type='list',
                                export_anything=False,
                                ask_user_before_export=True,
                                default_max_export=100,
                                database='neo4j', URI="bolt://localhost:7687", USER="giovanni", PASSWD="BabeldistGraph"):

    fname = utils.get_next_logfile_number('exporting_neo4j', extension='log')

    start_synset_id = start_synset_id
    max_synset_visited, n = max_synsets_visited, 0
    visited = set()
    q = utils.Queue(queue_type, [BabelSynsetID(id) for id in start_synset_id])

    URI = URI
    AUTH = (USER, PASSWD)
    
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session(database=database) as session:
            _run_no_exception(session, 'CREATE CONSTRAINT FOR (s:Synset) REQUIRE s.synsetID IS UNIQUE')
            tx = session.begin_transaction()
            
            start_n, start_r = tx.run(_count_nodes_query).values()[0][0], tx.run(_count_edges_query).values()[0][0]
            
            with open(fname, 'x') as logfname:
                logfname.write(f'database={database}\n')
                logfname.write(f'start_node={start_synset_id}\n')
                logfname.write(f'max_visits={max_synset_visited}\n')
                logfname.flush()

                start_t = time.time()
                while q.q and n < max_synset_visited:
                    pb = utils.get_progress_bar(int((n / max_synset_visited) * 100))
                    print(pb, end='\r')                

                    try:
                        synset = q.pop_item().to_synset()
                        hyponym_edges = synset.outgoing_edges(BabelPointer.ANY_HYPONYM)
                        if len(hyponym_edges) == 0: continue
                        elif not export_anything and len(hyponym_edges) > 100:
                            if ask_user_before_export:
                                print(f'Synset {synset.id} {synset.main_sense().full_lemma} has {len(hyponym_edges)}. ', end=' ')
                                a = input('Export them all? (y/n) ')
                                if a.lower().startswith('n'):   
                                    hyponym_edges = hyponym_edges[:min(default_max_export, len(hyponym_edges))]
                            else:
                                hyponym_edges = hyponym_edges[:min(default_max_export, len(hyponym_edges))]
                        n += 1
                        lemma = synset.main_sense().full_lemma
                    except (TimeoutExpired, LostRemote, AttributeError) as e:
                        hyponym_edges = []

                    hyponym_data = []
                    for edge in hyponym_edges:                        
                        if edge.id_target not in visited and edge.id_target not in q.q:                        
                            q.add_item(edge.id_target)
                            visited.add(edge.id_target)
                        try:
                            hyponym_data.append([edge.id_target.id, edge.id_target.to_synset().main_sense().full_lemma])    
                        except AttributeError as e:
                            logfname.write(f'Synset {edge.id_target} has not any main sense.\n')
                            logfname.flush()
                            
                    try:
                        tx.run(_merge_graph_query, {
                            'synsetID': str(synset.id),
                            'hyponyms': hyponym_data,
                            'synset_lemma': lemma})
                    except Exception as e:
                        e.with_traceback()

                    if n % 1000 == 0:
                        tx.commit()
                        tx = session.begin_transaction()
                        

                end_n, end_r = tx.run(_count_nodes_query).values()[0][0], tx.run(_count_edges_query).values()[0][0]
                tx.commit()
                print(f'Added {end_n - start_n} nodes, added {end_r - start_r} edges')
                                
                if q.q == []: logfname.write('Queue empy\n')
                if n == max_synset_visited: logfname.write('Reached max visits\n')
                logfname.write(f'Added {end_n - start_n} nodes, added {end_r - start_r} edges\n')
                end_t = time.time()
                m, s = divmod(end_t - start_t, 60)
                logfname.write(f'total_time,{int(m)}m,{int(s)}s') 

exporting_babelnet_to_neo4j(
    max_synsets_visited=5000, 
    database='babelexpDB', 
    ask_user_before_export=False,
    default_max_export=200    
)