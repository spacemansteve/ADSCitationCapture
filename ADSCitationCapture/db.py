import os
from psycopg2 import IntegrityError
from dateutil.tz import tzutc
from ADSCitationCapture.models import Citation, CitationTarget, Event
from adsmsg import CitationChange
from adsputils import setup_logging

# ============================= INITIALIZATION ==================================== #
# - Use app logger:
#import logging
#logger = logging.getLogger('ads-citation-capture')
# - Or individual logger for this file:
from adsputils import setup_logging, load_config
proj_home = os.path.realpath(os.path.join(os.path.dirname(__file__), '../'))
config = load_config(proj_home=proj_home)
logger = setup_logging(__name__, proj_home=proj_home,
                        level=config.get('LOGGING_LEVEL', 'INFO'),
                        attach_stdout=config.get('LOG_STDOUT', False))


# =============================== FUNCTIONS ======================================= #
def store_event(app, data):
    """
    Stores a new event in the DB
    """
    stored = False
    with app.session_scope() as session:
        event = Event()
        event.data = data
        session.add(event)
        try:
            session.commit()
        except:
            logger.exception("Problem storing event '%s'", str(event))
        else:
            stored = True
    return stored

def store_citation_target(app, citation_change, content_type, raw_metadata, parsed_metadata, status):
    """
    Stores a new citation target in the DB
    """
    stored = False
    with app.session_scope() as session:
        citation_target = CitationTarget()
        citation_target.content = citation_change.content
        citation_target.content_type = content_type
        citation_target.raw_cited_metadata = raw_metadata
        citation_target.parsed_cited_metadata = parsed_metadata
        citation_target.status = status
        session.add(citation_target)
        try:
            session.commit()
        except IntegrityError as e:
            # IntegrityError: (psycopg2.IntegrityError) duplicate key value violates unique constraint "citing_content_unique_constraint"
            logger.error("Ignoring new citation target (citting '%s', content '%s' and timestamp '%s') because it already exists in the database (another new citation may have been processed before this one): '%s'", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString(), str(e))
        else:
            logger.info("Stored new citation target (citting '%s', content '%s' and timestamp '%s')", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString())
            stored = True
    return stored

def update_citation_target_metadata(app, content, raw_metadata, parsed_metadata, status=None):
    """
    Update metadata for a citation target
    """
    metadata_updated = False
    with app.session_scope() as session:
        citation_target = session.query(CitationTarget).filter(CitationTarget.content == content).first()
        if type(raw_metadata) is bytes:
            try:
                raw_metadata = raw_metadata.decode('utf-8')
            except UnicodeEncodeError:
                pass
        if citation_target.raw_cited_metadata != raw_metadata or citation_target.parsed_cited_metadata != parsed_metadata or \
                (status is not None and citation_target.status != status):
            citation_target.raw_cited_metadata = raw_metadata
            citation_target.parsed_cited_metadata = parsed_metadata
            if status is not None:
                citation_target.status = status
            session.add(citation_target)
            session.commit()
            metadata_updated = True
            logger.info("Updated metadata for citation target '%s' (alternative bibcodes '%s')", content, ", ".join(parsed_metadata.get('alternate_bibcode', [])))
    return metadata_updated


def store_citation(app, citation_change, content_type, raw_metadata, parsed_metadata, status):
    """
    Stores a new citation in the DB
    """
    stored = False
    with app.session_scope() as session:
        citation = Citation()
        citation.citing = citation_change.citing
        citation.cited = citation_change.cited
        citation.content = citation_change.content
        citation.resolved = citation_change.resolved
        citation.timestamp = citation_change.timestamp.ToDatetime().replace(tzinfo=tzutc())
        citation.status = status
        session.add(citation)
        try:
            session.commit()
        except IntegrityError as e:
            # IntegrityError: (psycopg2.IntegrityError) duplicate key value violates unique constraint "citing_content_unique_constraint"
            logger.error("Ignoring new citation (citting '%s', content '%s' and timestamp '%s') because it already exists in the database when it is not supposed to (race condition?): '%s'", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString(), str(e))
        else:
            logger.info("Stored new citation (citting '%s', content '%s' and timestamp '%s')", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString())
            stored = True
    return stored

def get_citation_target_count(app):
    """
    Return the number of citation targets registered in the database
    """
    citation_target_count = 0
    with app.session_scope() as session:
        citation_target_count = session.query(CitationTarget).count()
    return citation_target_count

def get_citation_count(app):
    """
    Return the number of citations registered in the database
    """
    citation_count = 0
    with app.session_scope() as session:
        citation_count = session.query(Citation).count()
    return citation_count

def _extract_key_citation_target_data(records_db, disable_filter=False):
    """
    Convert list of CitationTarget to a list of dictionaries with key data
    """
    records = [
        {
            'bibcode': record_db.parsed_cited_metadata.get('bibcode', None),
            'alternate_bibcode': record_db.parsed_cited_metadata.get('alternate_bibcode', []),
            'content': record_db.content,
            'content_type': record_db.content_type,
        }
        for record_db in records_db
        if disable_filter or record_db.parsed_cited_metadata.get('bibcode', None) is not None
    ]
    return records

def get_citation_targets_by_bibcode(app, bibcodes, only_status='REGISTERED'):
    """
    Return a list of dict with the requested citation targets based on their bibcode
    """
    with app.session_scope() as session:
        records_db = []
        for bibcode in bibcodes:
            if only_status:
                record_db = session.query(CitationTarget).filter(CitationTarget.parsed_cited_metadata["bibcode"].astext == bibcode).filter_by(status=only_status).first()
            else:
                record_db = session.query(CitationTarget).filter(CitationTarget.parsed_cited_metadata["bibcode"].astext == bibcode).first()
            if record_db:
                records_db.append(record_db)

        if only_status:
            disable_filter = only_status == 'DISCARDED'
        else:
            disable_filter = True
        records = _extract_key_citation_target_data(records_db, disable_filter=disable_filter)
    return records

def get_citation_targets_by_doi(app, dois, only_status='REGISTERED'):
    """
    Return a list of dict with the requested citation targets based on their DOI
    - Records without a bibcode in the database will not be returned
    """
    with app.session_scope() as session:
        if only_status:
            records_db = session.query(CitationTarget).filter(CitationTarget.content.in_(dois)).filter_by(status=only_status).all()
            disable_filter = only_status == 'DISCARDED'
        else:
            records_db = session.query(CitationTarget).filter(CitationTarget.content.in_(dois)).all()
            disable_filter = True

        records = _extract_key_citation_target_data(records_db, disable_filter=disable_filter)
    return records

def get_citation_targets(app, only_status='REGISTERED'):
    """
    Return a list of dict with all citation targets (or only the registered ones)
    - Records without a bibcode in the database will not be returned
    """
    with app.session_scope() as session:
        if only_status:
            records_db = session.query(CitationTarget).filter_by(status=only_status).all()
            disable_filter = only_status == 'DISCARDED'
        else:
            records_db = session.query(CitationTarget).all()
            disable_filter = True
        records = _extract_key_citation_target_data(records_db, disable_filter=disable_filter)
    return records

def get_citation_target_metadata(app, doi):
    """
    If the citation target already exists in the database, return the raw and
    parsed metadata together with the status of the citation target in the
    database.
    If not, return an empty dictionary.
    """
    citation_in_db = False
    metadata = {}
    with app.session_scope() as session:
        citation_target = session.query(CitationTarget).filter_by(content=doi).first()
        citation_target_in_db = citation_target is not None
        if citation_target_in_db:
            metadata['raw'] = citation_target.raw_cited_metadata
            metadata['parsed'] = citation_target.parsed_cited_metadata if citation_target.parsed_cited_metadata is not None else {}
            metadata['status'] = citation_target.status
    return metadata

def get_citation_target_entry_date(app, doi):
    """
    If the citation target already exists in the database, return the entry date.
    If not, return None.
    """
    citation_in_db = False
    entry_date = None
    with app.session_scope() as session:
        citation_target = session.query(CitationTarget).filter_by(content=doi).first()
        citation_target_in_db = citation_target is not None
        if citation_target_in_db:
            entry_date = citation_target.created
    return entry_date

def get_citations_by_bibcode(app, bibcode):
    """
    Transform bibcode into content and get all the citations by content.
    It will ignore DELETED and DISCARDED citations and citations targets.
    """
    citations = []
    if bibcode is not None:
        with app.session_scope() as session:
            #bibcode = "2015zndo.....14475J"
            citation_target = session.query(CitationTarget).filter(CitationTarget.parsed_cited_metadata['bibcode'].astext == bibcode).filter_by(status="REGISTERED").first()
            if citation_target:
                dummy_citation_change = CitationChange(content=citation_target.content)
                citations = get_citations(app, dummy_citation_change)
    return citations

def get_citations(app, citation_change):
    """
    Return all the citations (bibcodes) to a given content.
    It will ignore DELETED and DISCARDED citations.
    """
    with app.session_scope() as session:
        citation_bibcodes = [r.citing for r in session.query(Citation).filter_by(content=citation_change.content, status="REGISTERED").all()]
    return citation_bibcodes


def citation_already_exists(app, citation_change):
    """
    Is this citation already stored in the DB?
    """
    citation_in_db = False
    with app.session_scope() as session:
        citation = session.query(Citation).filter_by(citing=citation_change.citing, content=citation_change.content).first()
        citation_in_db = citation is not None
    return citation_in_db

def update_citation(app, citation_change):
    """
    Update cited information
    """
    updated = False
    with app.session_scope() as session:
        citation = session.query(Citation).with_for_update().filter_by(citing=citation_change.citing, content=citation_change.content).first()
        change_timestamp = citation_change.timestamp.ToDatetime().replace(tzinfo=tzutc()) # Consider it as UTC to be able to compare it
        if citation.timestamp < change_timestamp:
            #citation.citing = citation_change.citing # This should not change
            #citation.content = citation_change.content # This should not change
            citation.cited = citation_change.cited
            citation.resolved = citation_change.resolved
            citation.timestamp = change_timestamp
            session.add(citation)
            session.commit()
            updated = True
            logger.info("Updated citation (citting '%s', content '%s' and timestamp '%s')", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString())
        else:
            logger.info("Ignoring citation update (citting '%s', content '%s' and timestamp '%s') because received timestamp is equal/older than timestamp in database", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString())
    return updated

def mark_citation_as_deleted(app, citation_change):
    """
    Update status to DELETED for a given citation
    """
    marked_as_deleted = False
    previous_status = None
    with app.session_scope() as session:
        citation = session.query(Citation).with_for_update().filter_by(citing=citation_change.citing, content=citation_change.content).first()
        previous_status = citation.status
        change_timestamp = citation_change.timestamp.ToDatetime().replace(tzinfo=tzutc()) # Consider it as UTC to be able to compare it
        if citation.timestamp < change_timestamp:
            citation.status = "DELETED"
            citation.timestamp = change_timestamp
            session.add(citation)
            session.commit()
            marked_as_deleted = True
            logger.info("Marked citation as deleted (citting '%s', content '%s' and timestamp '%s')", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString())
        else:
            logger.info("Ignoring citation deletion (citting '%s', content '%s' and timestamp '%s') because received timestamp is equal/older than timestamp in database", citation_change.citing, citation_change.content, citation_change.timestamp.ToJsonString())
    return marked_as_deleted, previous_status

def mark_all_discarded_citations_as_registered(app, content):
    """
    Update status to REGISTERED for all discarded citations of a given content
    """
    marked_as_registered = False
    previous_status = None
    with app.session_scope() as session:
        citations = session.query(Citation).with_for_update().filter_by(status='DISCARDED', content=content).all()
        for citation in citations:
            citation.status = 'REGISTERED'
            session.add(citation)
        session.commit()
